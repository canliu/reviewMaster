# Stage 5 — Request Review: Manual Mark, Link Redirect, Correction Notes, CSV Export

> Builds on Stages 0–4. This stage wires up the action buttons on the repeat-orders list and completes the MVP. SP-API integration is post-MVP and not included here.

## Goal

Sellers can mark orders as having had a review request, either by tagging them after doing it themselves in Seller Central (method=`manual`), or by clicking through to the Amazon order page (method=`link`). They can also append correction notes to existing request records, and export filtered repeat-order lists as CSV.

## Backend endpoints

### `POST /api/review-requests`

Create one or many review-request records.

Request body:
```json
{
  "order_uuids": ["uuid1", "uuid2", "..."],
  "method": "manual" | "link",
  "note": "optional initial note"
}
```

Validation, in this exact order:
1. **Ownership** — every `order_uuid` must belong to the current user. Any that don't → 403 `FORBIDDEN`.
2. **Repeat status** — every order must be a repeat order under the user's current settings (its `(shop_site, buyer_key, grouping_value)` triple must appear in `buyer_product_stats` with `order_count >= 2`). Any that aren't → 422 `NOT_A_REPEAT_ORDER`.
3. **Window** — every order's `estimated_delivery_utc` must be present, and `now() - estimated_delivery_utc` must be in `[5 days, 30 days]`. Any that fail → 422 `OUT_OF_WINDOW` with the specific reason per order_uuid.
4. **Active request check** — orders that already have a `review_request` row with status `'sent'` or `'pending'` are silently skipped (not failures — they're already done). They appear in the response under `skipped`. Orders whose most recent `review_request` is `failed` proceed to retry: see "Failed retry handling" below.

### Failed retry handling

The `UNIQUE(user_id, order_uuid)` constraint on `review_requests` means there can only be one row per order. To support retrying after a failure without losing audit history, we **soft-version** failed requests:

- When inserting a new `review_request` for an order whose existing row has status `'failed'`: in the same transaction, first append a row to `review_request_notes` (linked to the order, kind='system') summarizing the failure (`"Superseded retry: previous attempt failed with code <error_code> on <timestamp>"`), then **DELETE the old `review_request` row** and INSERT the new one.
- Because `review_request_notes` is attached to the order (not to the review_request), the failure history persists through the delete-and-reinsert.
- Document this in the service-layer code with a clear comment.

Alternative considered: removing the UNIQUE constraint and adding a `is_active` column. Rejected because it makes every read query more complex and provides no real benefit for a low-frequency event.

Behavior by method:

- `manual`: Insert a `review_request` row with `status='sent'`, `requested_at=now()`. If `note` is provided, also insert a `review_request_notes` row (linked to the order, kind='user').
- `link`: Insert a `review_request` row with `status='pending'`, `requested_at=now()`. Compute the redirect URL (see below) and return it. The seller will call `PATCH /api/review-requests/{id}/confirm` after they've clicked Request a Review in Seller Central.

Response:
```json
{
  "created": [
    { "id": "review-uuid", "order_uuid": "...", "method": "manual", "status": "sent", "redirect_url": null },
    { "id": "...", "order_uuid": "...", "method": "link", "status": "pending", "redirect_url": "https://sellercentral.amazon.com/orders-v3/order/112-..." }
  ],
  "skipped": [
    { "order_uuid": "...", "reason": "already requested" }
  ],
  "errors": [
    { "order_uuid": "...", "code": "OUT_OF_WINDOW", "reason": "too late (32 days)" }
  ]
}
```

Use a single database transaction. If any `errors` are reported, still commit the successful creations — the seller's bulk action should not be all-or-nothing for business-rule failures.

### `PATCH /api/review-requests/{id}/confirm`

Marks a `pending` link-method request as `sent`. Used after the seller has clicked Request a Review in Amazon.

- 404 if not found or not owned.
- 422 if status is not `pending`.
- Sets `status='sent'`, updates `updated_at`.

### `POST /api/orders/{order_uuid}/notes`

Append a correction or audit note tied to the order (not to a specific review_request — see Stage 0's schema rationale). There is no edit or delete — the log is append-only.

Body: `{ "note": "string, 1–500 chars" }`. The server records `kind='user'` and stores `review_request_id` (if any active request exists for that order at the moment of writing).

### `GET /api/orders/{order_uuid}/notes`

Returns all notes for an order, oldest first. Notes survive retries — if a review_request was deleted-and-reinserted on retry, its notes persist linked to the order.

### `GET /api/review-requests`

List the current user's review requests, paginated, with filters:
- `method`: manual | link | api
- `status`: pending | sent | failed
- `shop_site`: filter to one shop
- `from_date`, `to_date`: filter `requested_at` range

Returns each request joined with its order's `order_id`, `product_name`, `buyer_email`, `shop_site`, plus a `notes_count` (count of notes on the related order).

### `GET /api/review-requests/{id}`

Detail view: the request plus all notes attached to the same order (sorted by `created_at` ascending) and the related order.

### `GET /api/review-requests/export.csv`

Same filters as the list endpoint, but streams a CSV with columns:
`order_id, shop_site, asin, product_name, buyer_email, buyer_key, ship_city, ship_state, ship_country, order_time_utc, estimated_delivery_utc, item_price, currency, quantity, request_method, request_status, requested_at, notes_count`.

Sets `Content-Disposition: attachment; filename="review-requests-{YYYY-MM-DD}.csv"`.

### `GET /api/repeat-orders/export.csv`

Same filters as `GET /api/repeat-orders` (Stage 4). Same CSV-stream behavior. Columns:
`order_id, shop_site, asin, product_name, buyer_email, buyer_key, ship_city, ship_state, ship_country, order_time_utc, estimated_delivery_utc, item_price, currency, quantity, purchase_index, total_purchases, request_method, request_status, can_request_review, can_request_reason`.

### `GET /api/buyers/{buyer_key}/orders.csv`

A convenience export for the slide-over buyer-history view: streams the same shape as the repeat-orders export, scoped to a single buyer in the active shop. Allows a seller to do offline outreach research on a specific customer.

## Redirect URL builder

For method=`link`, build the Seller Central order URL:

```
https://sellercentral.amazon.{tld}/orders-v3/order/{order_id}
```

Where `{tld}` is derived from the marketplace inferred from `shop_site`:

| Marketplace token in shop_site | TLD |
|---|---|
| US | com |
| CA | ca |
| MX | com.mx |
| BR | com.br |
| UK or GB | co.uk |
| DE | de |
| FR | fr |
| IT | it |
| ES | es |
| NL | nl |
| SE | se |
| PL | pl |
| TR | com.tr |
| AE | ae |
| SA | sa |
| EG | eg |
| JP | co.jp |
| AU | com.au |
| SG | sg |
| IN | in |

`shop_site` looks like `"p3:US"` — split on `:` and take the right side, uppercase, then look up the TLD. Unknown → 422 `UNSUPPORTED_MARKETPLACE` with a clear message.

Implement this as a pure function in `services/seller_central.py` with full test coverage.

Important: This URL goes to the order detail page, not directly to the "Request a Review" action — Amazon does not provide a deep link to the action itself. Document this in the function's docstring. The frontend's confirmation modal needs to instruct the seller to click the "Request a Review" button on the page.

## Frontend wiring

### On the repeat-orders table (Stage 4)

Wire the row-level action buttons that were stubs:

1. **Manual mark button** — calls `POST /api/review-requests` with `{ order_uuids: [this_row], method: 'manual' }`. Show a toast on success. Optimistically updates the row's Status badge to `Requested · manual`.

2. **Open Amazon button** — calls `POST /api/review-requests` with `method: 'link'`. On response, `window.open(redirect_url, '_blank')` and pop a modal:

   > "Amazon's order page is open in a new tab. Click the **Request a Review** button there, then return and confirm below."
   >
   > Buttons: **I clicked it** | **Cancel**

   - **I clicked it** → `PATCH /api/review-requests/{id}/confirm` → status becomes `sent`, badge updates.
   - **Cancel** → leaves the request in `pending` state. The seller can re-open from the row later.

   **Reopening a pending link request**: when a row has a `pending` link-method request, the Status badge becomes clickable. Clicking it reopens the same modal with the original `redirect_url` (cached on the request via `api_response.redirect_url`) so the seller can complete the flow without creating a new request. The "Mark as requested (manual)" action is also available on pending rows — if the seller realizes they did it themselves, they can confirm with method=manual via `PATCH /api/review-requests/{id}/confirm-as-manual` (add this small endpoint: it updates `method` from `link` to `manual` and sets status to `sent`).

3. **Batch action bar** (top of table, visible when ≥1 row selected) gets a `Mark selected as requested (manual)` button. Optionally a textarea for a shared note. Calls the same endpoint with all selected `order_uuids`.

### New page `/dashboard/review-requests`

List all review requests with the filters listed above. Each row has:
- Order id, product, buyer, shop
- Method badge, Status badge
- Requested at (formatted in user's timezone)
- Notes count
- "Add note" button

Clicking a row opens a slide-over with:
- All notes, with timestamps
- A textarea to add a new note

### Export buttons

- On `/dashboard/repeat-orders`: an "Export CSV" button in the toolbar. Hitting it triggers `GET /api/repeat-orders/export.csv` with the current filters' query string.
- On `/dashboard/review-requests`: same, for that endpoint.

Browsers handle the file download natively — no React state changes needed.

### Optimistic updates

Use TanStack Query's mutation `onMutate` / `onError` to optimistically flip the row's Status badge immediately. Roll back on failure.

## Tests

`backend/tests/test_review_requests.py`:

- Marking a non-repeat order is rejected with `NOT_A_REPEAT_ORDER`.
- Marking an order outside the 5–30 day window is rejected with `OUT_OF_WINDOW`.
- Marking an already-sent order is reported as `skipped`, not as an error.
- A bulk request with mixed valid/invalid orders creates the valid ones and reports the invalid ones in `errors`.
- The redirect URL is correct for US, UK, DE, JP shop_sites and rejects unknown markets.
- A pending (link) request can be confirmed and transitions to sent.
- Confirming an already-sent request returns 422.
- Notes are append-only — there is no PATCH or DELETE on notes.
- **Failed retry**: seed a `failed` review_request with two attached notes → submit a fresh manual mark on the same order → verify the old `review_request` row is gone, a new `sent` row exists, the two original notes still exist, and a third system note about the supersession was inserted.
- Cross-user isolation: user A cannot create a review request on user B's order, even with a guessed `order_uuid`.

`backend/tests/test_csv_export.py`:
- CSV header matches the spec.
- Row count matches the count from the corresponding list endpoint with the same filters.

## Acceptance checks

1. Pick a repeat order in the window. Click "Mark as requested". Status badge flips immediately; refresh confirms it persisted; the same button is now disabled.
2. Pick another order. Click "Open Amazon". A new tab opens to the correct Seller Central URL for that order. Return, click "I clicked it", badge becomes `Requested · link`.
3. Select 10 rows and use the batch action. All 10 are marked.
4. Try to mark an already-sent order in a bulk action — it appears in `skipped`, not `errors`.
5. Try to mark an order whose delivery date is 2 days ago — it appears in `errors` with `OUT_OF_WINDOW`.
6. Export both CSVs with various filters and confirm the row counts and columns.
7. Add three notes to a single request; verify all three show in chronological order; verify nothing was deleted.

## MVP complete

After this stage, the seller has a fully working tool: upload → see repeat orders → mark or link-request reviews → export records. Stages 6 (SP-API) and 7 (analytics, multi-user team features, etc.) are post-MVP and intentionally not included.

## Out of scope for MVP

- No SP-API integration.
- No automatic re-scan when settings change (the list re-queries naturally, but no background job).
- No email digest of pending tasks.
- No A/B testing of review-request timing.
