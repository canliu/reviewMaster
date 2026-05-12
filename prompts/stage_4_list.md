# Stage 4 — Repeat Orders List

> Builds on Stages 0–3. This is the centerpiece feature of the app: the page sellers will spend most of their time on.

## Goal

A logged-in seller, with at least one upload done and settings configured, can see a paginated, filterable, sortable list of repeat orders for the active shop. For each order they see whether it can be requested for review right now, and whether it has already been requested.

## Definition (repeat — restated for clarity)

For a given user and the user's currently selected `repeat_grain`:

- Look at `buyer_product_stats` rows where `grain` matches the user's setting and `order_count ≥ 2`.
- Every original order in `orders` that maps to one of those `(shop_site, buyer_key, grouping_value)` tuples is a **repeat order**.
- The first purchase of a buyer-product pair is also a repeat order under this definition (it appears in the list with `purchase_index = 1` and `total_purchases ≥ 2`).
- Apply the `excluded_order_types` filter from settings.
- Scope to `active_shop_site` from settings.

## Backend endpoints

### `GET /api/repeat-orders/summary`

KPI cards at the top of the page. Computed for the active shop site, honoring excluded order types.

```json
{
  "total_repeat_orders": 1518,
  "total_repeat_buyers": 432,
  "total_repeat_products": 38,
  "in_review_window": 217,
  "already_requested": 89
}
```

### `GET /api/repeat-orders`

Query parameters:
- `page` (default 1), `page_size` (default 50, max 200)
- `asin` (optional, exact match)
- `product_search` (optional, ILIKE on `product_name` or `product_title`)
- `has_review_request` (optional: `true | false`)
- `in_window` (optional: `true | false`) — whether the order is currently within the request window
- `min_purchases` (optional integer, default 2) — only show buyer-product groups with at least this many orders
- `sort` (optional, default `last_order_desc`):
  - `last_order_desc` — most-recent purchase first
  - `purchase_count_desc` — buyers with most repeat purchases first, then by last_order_desc
  - `delivery_asc` — orders nearing the 30-day cutoff first

Response:
```json
{
  "total": 1518,
  "page": 1,
  "page_size": 50,
  "items": [ ... ]
}
```

Each item:
```json
{
  "order_uuid": "uuid",
  "order_id": "112-0113867-7307408",
  "shop_site": "p3:US",
  "asin": "B0CQW5NDWJ",
  "product_name": "NutraPep Magnesium Glycinate Gummies",
  "product_title_short": "NutraPep Magnesium Glycinate Gummies for Kids & Adults...",
  "order_type": "亚马逊销售订单",
  "buyer_email": "vqjdk1ymgqcrstz@marketplace.amazon.com",
  "buyer_key": "email:vqjdk1ymgqcrstz@marketplace.amazon.com",
  "order_time_utc": "2026-05-05T16:44:52Z",
  "estimated_delivery_utc": "2026-05-07T03:00:00Z",
  "item_price": 19.99,
  "currency": "USD",
  "quantity": 1,
  "ship_city": "ROCHESTER",
  "ship_state": "NY",
  "ship_country": "US",
  "purchase_index": 2,
  "total_purchases": 3,
  "review_request": null,
  "can_request_review": true,
  "can_request_reason": null
}
```

Field rules:
- `product_title_short` — truncate `product_title` to 80 characters, append `…` if truncated.
- `purchase_index` — this order's position among that buyer's purchases of this product, ordered by `order_time_utc` ascending. Computed with `ROW_NUMBER() OVER (PARTITION BY buyer_key, grouping_col ORDER BY order_time_utc)`.
- `total_purchases` — `buyer_product_stats.order_count` for that buyer-product pair.
- `review_request` — null if no active (sent or pending) request exists; otherwise `{ method, status, requested_at }`. A historical failed request that has been superseded does not appear here.
- `can_request_review` — `true` iff:
  - `estimated_delivery_utc` is not null, AND
  - `now() - estimated_delivery_utc` is between 5 days and 30 days (inclusive lower, exclusive upper), AND
  - No existing `review_request` with status `'sent'` or `'pending'` for this order. **A `review_request` with status `'failed'` does not block — failed requests are retryable, and the next successful request will create a new row (the UNIQUE constraint is on a column we delete-and-re-insert when retrying; see Stage 5 retry logic).**
- `can_request_reason` — when `can_request_review` is false, one of: `"missing delivery date"`, `"too early (< 5 days after delivery)"`, `"too late (> 30 days after delivery)"`, `"already requested"`.

### `GET /api/repeat-orders/{order_uuid}`

Detail view. Returns the same fields as a list item plus a **buyer history** section:

```json
{
  "order": { ...same as list item... },
  "buyer_history": {
    "buyer_key": "email:vqjdk1...",
    "buyer_email": "vqjdk1...@marketplace.amazon.com",
    "total_orders_all_products": 7,
    "orders_returned": 50,
    "has_more": false,
    "orders": [
      {
        "order_id": "...",
        "asin": "B0CQW5NDWJ",
        "product_name": "...",
        "order_time_utc": "...",
        "item_price": 19.99,
        "quantity": 1,
        "review_request_status": "sent" | "pending" | null
      },
      ...
    ]
  }
}
```

The buyer history lists this buyer's orders in this shop, across all products, newest first, **capped at 50**. `has_more` indicates truncation. For full history, the seller uses the buyer-specific CSV export (added in Stage 5).

## Performance

- The list endpoint must return in **under 500 ms** for a user with 30,000 orders and ~1,500 repeat orders, served from a cold cache.
- Use a single CTE-based SQL query rather than multiple round trips. The query plan should use the `(user_id, shop_site, buyer_key, asin)` index.
- Add a query-side LIMIT/OFFSET; do not load the full result set into memory.

## Frontend page: `/dashboard/repeat-orders`

### Layout

```
┌───────────────────────────────────────────────────────────┐
│ Header: Shop switcher (from Stage 3) | user menu          │
├───────────────────────────────────────────────────────────┤
│ KPI cards: Repeat Orders | Repeat Buyers | Repeat Products│
│            | In Window  | Already Requested                │
├───────────────────────────────────────────────────────────┤
│ Filter bar: ASIN | Search | Review status | In window |   │
│             Min purchases | Sort                          │
├───────────────────────────────────────────────────────────┤
│ Batch action bar (only when rows selected): "Mark N as    │
│ requested (manual)" — wired in Stage 5                    │
├───────────────────────────────────────────────────────────┤
│ TanStack Table:                                           │
│  [✓] Order | Buyer | Product | Purchases | Price |        │
│      Delivery ETA | Status | Actions                      │
├───────────────────────────────────────────────────────────┤
│ Pagination                                                │
└───────────────────────────────────────────────────────────┘
```

### Table specifics

- Row selection via checkboxes; header checkbox toggles current page only.
- The **Purchases** column shows a badge like `2 / 3` meaning this is purchase #2 out of 3 total. Color the badge:
  - Gray if `purchase_index == total_purchases` (latest purchase)
  - Blue otherwise (an earlier purchase in the sequence)
- The **Status** column shows a badge:
  - `Not requested` (gray) — when `review_request` is null
  - `Requested · manual` (blue) — when `review_request.status == 'sent'` and `method == 'manual'`
  - `Requested · link` (blue) — same for link
  - `Requested · API` (green) — when status is sent and method is api
  - `Pending` (yellow) — when status is pending (link not yet confirmed, or api in flight)
  - `Failed` (red) — when status is failed
- The **Actions** column has three icon buttons per row:
  - Manual mark (this stage 5 wires it)
  - Open Amazon (stage 5)
  - API send (stage 6, disabled with tooltip "Coming soon")
- When `can_request_review` is false, the whole row's actions are disabled and the row has `opacity-50`. Hovering shows `can_request_reason` in a tooltip.
- Click anywhere else on the row → slide-over panel showing the detail endpoint's response (buyer history).

### Filters' behavior

- Each filter change updates the URL query string so the view is shareable / bookmarkable.
- Filters debounce by 300 ms before triggering a fetch.
- TanStack Query caches by the full query-param set; switching between filter combos is instant on a re-visit.

### Empty states

- No upload yet → CTA pointing to `/dashboard/uploads`.
- Upload done but no repeat orders found → "No repeat orders match your filters. Try changing the grain in Settings or relaxing your filters."

## Tests

`backend/tests/test_repeat_orders.py`:

- A buyer with only one purchase of an ASIN does not appear in the list.
- A buyer with two purchases shows both orders in the list, with `purchase_index` 1 and 2 and `total_purchases` 2.
- Changing `repeat_grain` from `asin` to `spu` regroups results (write a fixture where buyer purchased two different ASINs sharing the same SPU).
- Adding an order type to `excluded_order_types` removes those orders from the list.
- `in_window` filter correctly excludes orders too early and too late.
- `has_review_request=false` excludes orders that already have any review_request row (regardless of its status).
- `can_request_review` is false when the order has a sent or pending review_request, true when it has only a failed one.
- Cross-user isolation: user A cannot see user B's orders even by guessing `order_uuid`.

## Acceptance checks

1. With the 30,000-row real file loaded and grain set to ASIN, the page renders in under 1 second.
2. KPI cards' numbers reconcile with hand-rolled SQL counts.
3. Switching grain to SPU on the settings page and returning here updates the list and KPI cards accordingly.
4. Excluding an order type on the settings page shrinks the list as expected.
5. The shop switcher in the header swaps the entire data context (assuming the user has uploads from multiple shops; otherwise just confirm the dropdown disables additional choices).
6. Clicking a row opens the slide-over with the full buyer history.

## Out of scope

- The action buttons themselves (manual / link / api) are wired in Stages 5 and 6.
- No CSV export yet (Stage 5).
- No saved filter presets.
