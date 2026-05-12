# Stage 6 — Amazon SP-API Integration (method=api)

> Runs **after** `stage_polish.md`. Adds the third review-request method: automatic submission via Amazon Selling Partner API.

## Goal

Sellers can configure their SP-API credentials in the app and then use the third "API" action on any repeat order to submit a review request via the official `Solicitations` API automatically. No more clicking through to Seller Central.

## Background

Amazon's SP-API Solicitations endpoint:

- **Endpoint:** `POST /solicitations/v1/orders/{amazonOrderId}/solicitations/productReviewAndSellerFeedback`
- **Rate limit:** 1 request/second, burst of 5
- **Authentication:** Login-with-Amazon (LWA) OAuth — exchange a long-lived refresh token for a short-lived access token; sign each request with AWS Signature V4 (using IAM credentials) or use a self-authorized app (no AWS IAM needed for self-registered apps as of 2024).
- **Docs:** https://developer-docs.amazon.com/sp-api/docs/solicitations-api-v1-reference

We'll use the `python-amazon-sp-api` library (`pip install python-amazon-sp-api`) to abstract away the LWA exchange and signing.

## Scope

1. Credential storage with envelope encryption
2. Credential UI (settings page)
3. Connection test endpoint
4. New `method="api"` path in the review-request flow
5. Worker job that calls SP-API with rate limiting and retry
6. Real-time status updates on the repeat-orders table
7. Multi-marketplace handling
8. Error catalog (decode common SP-API failure modes for the user)

## 1. Credential storage (envelope encryption)

The `seller_credentials` table already exists from Stage 0. Recap of the envelope-encryption model:

- A **KEK** (key encryption key) is stored in `ENCRYPTION_KEK` env var. 32-byte URL-safe base64.
- For each user, generate a **DEK** (data encryption key) — also 32 bytes — at credential-save time.
- Encrypt the user's actual secrets (`refresh_token`, `lwa_client_secret`) with the DEK using Fernet.
- Encrypt the DEK itself with the KEK, store as `dek_encrypted`.
- On read: decrypt DEK with KEK, then decrypt secrets with DEK.

Benefits over single-key Fernet:
- Rotating the KEK only requires re-wrapping each DEK, not re-encrypting all ciphertext.
- A KMS upgrade path: replace the KEK with a call to AWS KMS / GCP KMS later, no schema change.

Implement in `services/crypto.py` with these functions:

- `generate_dek() -> bytes`
- `wrap_dek(dek: bytes, kek: bytes) -> bytes`
- `unwrap_dek(wrapped: bytes, kek: bytes) -> bytes`
- `encrypt(plaintext: str, dek: bytes) -> bytes`
- `decrypt(ciphertext: bytes, dek: bytes) -> str`

Unit-test each with both valid and tampered inputs.

## 2. Credential UI

### Page `/dashboard/settings/sp-api`

Add a third tab to the settings page (alongside the existing settings tabs from Stage 3). Layout:

```
┌─────────────────────────────────────────────────┐
│ SP-API connection                                │
│                                                  │
│ Status: ⚠ Not connected                          │
│                                                  │
│ LWA Client ID         [.................]        │
│ LWA Client Secret     [•••••••••••••••••]        │
│ Refresh Token         [•••••••••••••••••]        │
│ Selling Partner ID    [.................]        │
│ Marketplace           [Dropdown: US/CA/...]      │
│                                                  │
│ [Test connection]      [Save]    [Disconnect]    │
└─────────────────────────────────────────────────┘
```

Behavior:
- When already connected, the secret fields show "•••• (saved)" and are not pre-filled with actual values. The Save button is disabled unless the user types fresh values into at least one secret field.
- "Test connection" calls a backend endpoint that decrypts and tries `getMarketplaceParticipations`. Returns ok or a clear error.
- "Disconnect" deletes the row from `seller_credentials`.

Provide a help link below the form: "How to get my SP-API credentials" pointing to a short markdown page (next item).

### Help page `/dashboard/help/sp-api-setup`

A static markdown page rendered inside the app shell. Steps:

1. Register as a Developer in Seller Central (Apps & Services → Develop Apps).
2. Create a "self-authorization" app (the easy path — no marketplace listing review needed).
3. Generate LWA credentials.
4. Self-authorize to get a refresh token.
5. Note your Selling Partner ID and Marketplace ID.
6. Paste them into ReviewMaster.

Keep it brief and screenshot-free (we're not making a polished docs site). Link out to Amazon's official docs for the deep dive.

## 3. Backend endpoints

### `POST /api/sp-api/credentials`

Body: `{ lwa_client_id, lwa_client_secret, refresh_token, selling_partner_id, marketplace_id }`.

Validation: all required, non-empty. Marketplace ID must match a known marketplace.

Behavior:
- If a row already exists for the user, update it (re-encrypt with a fresh DEK).
- Else insert a new row.
- Never return the secrets in any response.

### `GET /api/sp-api/credentials`

Returns metadata only — never the secrets:
```json
{
  "configured": true,
  "lwa_client_id_prefix": "amzn1.application-oa2-client.abc...",
  "selling_partner_id": "A1B2C3...",
  "marketplace_id": "ATVPDKIKX0DER",
  "marketplace_label": "Amazon.com (US)",
  "updated_at": "..."
}
```

### `POST /api/sp-api/test-connection`

Decrypt credentials, instantiate the python-amazon-sp-api client, call `Sellers.get_marketplace_participations()`. Return:
```json
{
  "ok": true,
  "marketplaces": ["ATVPDKIKX0DER", "A2EUQ1WTGCTBG2", ...],
  "elapsed_ms": 412
}
```

On failure:
```json
{
  "ok": false,
  "error_code": "INVALID_REFRESH_TOKEN" | "RATE_LIMITED" | "NETWORK" | "UNKNOWN",
  "message": "Refresh token rejected by Amazon. Please re-authorize."
}
```

### `DELETE /api/sp-api/credentials`

Deletes the row. Returns 204.

## 4. Submitting an API review request

Extend the existing `POST /api/review-requests` from Stage 5 to support `method: "api"`.

Validation additions on top of Stage 5's rules:
- User must have a `seller_credentials` row → otherwise 422 `SP_API_NOT_CONFIGURED`.
- **No marketplace pre-check at the API boundary.** SP-API may be authorized for marketplaces other than the credential's stored `primary`. If the order's marketplace is not authorized, Amazon will return an `Unauthorized` error and the worker translates it to `MARKETPLACE_MISMATCH` and surfaces it to the user with guidance. This avoids false negatives where a seller has correctly authorized US+CA but the credential row's primary says only US.

For each order_uuid that passes validation:
- Insert a `review_request` row with `status="pending"`, `method="api"`.
- Enqueue an RQ job `send_solicitation(review_request_id)`.

Return the same response shape as Stage 5, with each created item showing `status: "pending"`. The frontend polls or uses WebSockets to update — see section 6.

## 5. The worker job

`workers/solicitations.py` defines `send_solicitation(review_request_id: UUID)`.

Logic:

1. Load the `review_request` row and join its order.
2. Load and decrypt the user's `seller_credentials`.
3. Acquire a rate-limit slot — see below.
4. Instantiate the SP-API `Solicitations` client.
5. Call `create_product_review_and_seller_feedback_solicitation(order_id=order.order_id, marketplace_ids=[marketplace_id])`.
6. On success: update `review_request.status="sent"`, `api_response = {...the response body...}`, `updated_at=now()`.
7. On failure: map the exception to an `error_code` (table below), update `status="failed"`, store the original error in `api_response`.

### Rate limiting

SP-API caps Solicitations at 1 req/s steady, burst 5. We respect this across **all** users of this single deployment (Amazon rate-limits per developer account, not per seller account).

Implementation: Redis-backed token bucket in `services/rate_limit.py`:

- A single key `sp_api_solicitations:tokens` (no per-user partitioning).
- Refill rate: 1 token per second, max 5.
- Each worker job acquires 1 token before calling the API. If no token available, sleep 100ms and retry, with a max wait of 60s before giving up (then the job re-enqueues itself for later).

If multiple workers are running, the Redis script ensures atomicity. Use a Lua script for the token-bucket get-or-wait operation.

### Retries

Map SP-API failures into three categories:

| Category | Examples | Retry? |
|---|---|---|
| Permanent client error | 400 invalid order ID, 403 missing scope, order not eligible (e.g. cancelled) | No |
| Auth error | 401 — usually a stale access token; the lib auto-refreshes; if it still fails, surface to user | No (after one in-lib retry) |
| Rate limit | 429 | Yes — exponential backoff: 2s, 5s, 15s, give up |
| Transient server | 500, 502, 503, 504, network timeouts | Yes — same backoff |

Implement with `tenacity` (`pip install tenacity`).

### Special handling for `ALREADY_SOLICITED`

Amazon will return an error if a review has already been requested for an order (whether by us, by another tool, or manually in Seller Central within the past 24 hours / 30 days). Distinct from a real failure:

- When the worker receives a response that maps to `ALREADY_SOLICITED`, set `review_request.status = "sent"` (not `"failed"`), set `error_code = "ALREADY_SOLICITED_BY_AMAZON"`, and store Amazon's response in `api_response`.
- Logically: the seller asked us to request a review; the review has effectively been requested (by someone). The user's intent is satisfied. Treating this as `failed` would tempt the seller to retry — which Amazon would reject again, possibly with a stricter penalty.
- The UI's Status badge for these rows shows `Requested · API` (green) but the row's detail popover surfaces a small info note: "Amazon reports this order was already solicited elsewhere. No new request was sent."

### Standard error code catalog

```python
ERROR_CODES = {
    "OUT_OF_WINDOW": "Order is outside the 5–30 day window.",
    "ORDER_NOT_FOUND": "Amazon doesn't recognize this order ID.",
    "ALREADY_SOLICITED": "Amazon reports a review has already been requested for this order.",
    "INELIGIBLE_ORDER": "Amazon won't accept review requests for this order (cancelled, refunded, etc.).",
    "INVALID_REFRESH_TOKEN": "Your refresh token is invalid or revoked. Please reconnect in Settings.",
    "RATE_LIMITED": "Amazon rate-limited the request. We'll retry automatically.",
    "MARKETPLACE_MISMATCH": "The order's marketplace doesn't match your SP-API credentials.",
    "NETWORK_ERROR": "We couldn't reach Amazon. Please try again later.",
    "UNKNOWN": "Something went wrong. Check the details below.",
}
```

The worker stores the matched code on the `review_request` row in a new column `error_code` (add via a new Alembic migration in this stage).

## 6. Real-time status updates

The user just clicked "API send" on 10 rows. They want to see status flip from `pending` → `sent` / `failed` without refreshing.

Two acceptable approaches; pick **polling** for MVP simplicity:

- TanStack Query refetches `/api/repeat-orders` every 3 seconds **only while at least one visible row has `review_request.status === "pending"`**. Stop polling when none are pending.
- On the review-requests detail page, same logic per individual request.

(Skip WebSockets / SSE for now; they're worth doing if usage grows.)

## 7. Frontend wiring

### On the repeat-orders table

- The "API send" button (previously disabled in Stage 4) is now active **iff** SP-API is configured. We do not pre-disable based on marketplace — the worker handles `MARKETPLACE_MISMATCH` after attempt.
- If SP-API isn't configured: button is disabled with tooltip "Configure SP-API in Settings to use this method."
- If the worker later returns `MARKETPLACE_MISMATCH`: the row shows status `Failed`. Clicking the badge opens a popover: "This marketplace isn't authorized in your SP-API app yet. Go to Seller Central → Manage Your Apps to grant access, then retry."
- On click: confirms with a small dialog ("Send via Amazon API for order 112-…?"), then POSTs.
- Status badge transitions: `Not requested` → `Pending` (amber, with a small spinner icon) → `Requested · API` (green) or `Failed` (red).
- A `Failed` badge is clickable — opens a small popover showing the error code and the original Amazon error message.

### Batch action bar

- New batch action: "Send via API". Same eligibility filtering — disabled if any selected row is ineligible.
- Confirmation dialog shows breakdown: "12 selected · 10 eligible · 2 will be skipped (already requested / outside window)." Marketplace authorization is not pre-checked — Amazon's response is the source of truth.

### Settings page

- The SP-API status indicator appears in the sidebar near the user menu: a tiny dot, green if connected, gray if not.

## 8. Multi-marketplace handling

A seller may have multiple shops (e.g. US + CA + UK) but our current model allows only **one** SP-API credential set per user. This is a deliberate MVP limit — most sellers use the same developer app across marketplaces, and SP-API does support cross-marketplace calls with one credential set as long as the seller has authorized each marketplace in Seller Central.

### Semantics of the `marketplace_id` field

The single `marketplace_id` stored in `seller_credentials` is the seller's **primary marketplace** — the one we test the connection against and the default we display in the UI. It is **not** a limit on which marketplaces we can send solicitations to.

When the worker submits a solicitation for an order:
- It calls SP-API with `marketplace_ids=[<order's marketplace, derived from shop_site>]`, **not** the stored primary.
- If the call fails with "not authorized for this marketplace" (Amazon error code `Unauthorized`), surface as `MARKETPLACE_MISMATCH` and tell the user to authorize the additional marketplace in Seller Central → Manage Your Apps.

### UI

The credential form's marketplace dropdown is **single-select** and labeled "Primary marketplace (used for connection testing)" so the seller understands it's not the only one they can use. A help hint below: "To request reviews in other marketplaces, ensure your Seller Central app is authorized there too."

## Tests

`backend/tests/test_crypto.py`:
- DEK wrap/unwrap roundtrips correctly.
- Tampered DEK ciphertext fails to unwrap.
- Encrypted secret roundtrips; tampered ciphertext fails.

`backend/tests/test_sp_api_credentials.py`:
- Save → fetch metadata → secrets are not in the response.
- Save with bad marketplace → 422.
- Connection test happy path (mock the SP-API client).
- Connection test with rejected refresh token → returns the right error_code.

`backend/tests/test_solicitations_worker.py`:
- Happy path: mock the SP-API call, verify status becomes `sent`.
- Rate-limited path: simulate 429 once, then success — verify retry happens.
- Permanent failure: simulate 400 ineligible — verify status `failed` and correct error_code.
- Rate limiter under concurrency: 10 jobs at once → no more than 5 fire in the first second.

Use `responses` or `httpretty` to mock the underlying HTTP calls.

## Migration

Add `error_code text NULL` column to `review_requests` via a new Alembic migration. Backfill is unnecessary — existing rows have no errors recorded.

## Acceptance checks

1. Without SP-API configured, the "API send" button is disabled with the right tooltip.
2. Configure SP-API with valid credentials → status indicator turns green; test connection returns OK.
3. Configure with an invalid refresh token → test connection returns `INVALID_REFRESH_TOKEN` with a helpful message.
4. Send via API on one order → status flips to `Pending`, then to `Requested · API` within ~3 seconds (poll-driven).
5. Send a batch of 10 → all eventually resolve; rate limiter prevents overshoot.
6. Force a failure (use a known-bad order ID via DB tweak) → status `Failed`, popover shows decoded error.
7. `docker compose exec postgres psql ...` shows no plaintext secrets in `seller_credentials`.
8. Disconnect → row is gone, button is re-disabled.

## Out of scope

- Multi-credential support (one per marketplace).
- WebSocket / SSE real-time push.
- Automatic scheduled batches (e.g. "send API requests to all eligible orders every Monday at 9 AM").
- Listings API or other SP-API endpoints beyond Solicitations and Sellers.
