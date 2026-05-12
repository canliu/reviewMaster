# Stage 3 — User Settings

> Builds on Stages 0–2. This stage adds the controls that govern how repeat orders are detected and displayed.

## Goal

A seller can configure:
1. **Active shop site** — switches which marketplace they are working on. Drives the global filter for the repeat-orders list.
2. **Repeat grain** — `asin`, `spu`, or `product_name`. Controls how "same product" is defined.
3. **Excluded order types** — orders matching these types are hidden from the repeat list (e.g. cancellations, refunds).
4. **Timezone** — for date display in the UI.

These settings live in the `user_settings` table and are loaded on every authenticated request.

## Backend endpoints

### Note on storage layout

The settings exposed by this stage live in two tables:
- `users.timezone` — the IANA timezone string
- `user_settings.active_shop_site`, `user_settings.repeat_grain`, `user_settings.excluded_order_types`

The API surfaces them as one logical "settings" object. The service layer joins `users` and `user_settings` by `user_id` when reading and writes back to whichever table owns each field.

### `GET /api/settings`
Returns the current user's settings plus dynamically computed options:

```json
{
  "active_shop_site": "p3:US",
  "repeat_grain": "asin",
  "excluded_order_types": ["退货", "已取消"],
  "timezone": "America/New_York",
  "available_shop_sites": ["p3:US", "p3:CA"],
  "available_order_types": ["亚马逊销售订单", "退货", "已取消"]
}
```

- `available_shop_sites` is derived: `SELECT DISTINCT shop_site FROM orders WHERE user_id = :uid ORDER BY shop_site`.
- `available_order_types` is derived: `SELECT DISTINCT order_type FROM orders WHERE user_id = :uid AND order_type IS NOT NULL ORDER BY order_type`.
- If the user has no orders yet, both lists are empty and `active_shop_site` may be null.

### `PATCH /api/settings`
Accepts a partial update of any combination of these fields:
- `active_shop_site` — must be one of `available_shop_sites` if not null.
- `repeat_grain` — must be `'asin' | 'spu' | 'product_name'`.
- `excluded_order_types` — list of strings, each must currently exist in `available_order_types`.
- `timezone` — must be a valid IANA name (validate with `zoneinfo.ZoneInfo`).

Validation errors → HTTP 422 with specific field messages.

On success, returns the same shape as `GET /api/settings`.

## Auto-activate first shop on first upload

This hook is **already implemented in Stage 2's upload worker** (step 8 of the worker pipeline). Recap of the rule, so the contract is clear in one place:

- After a successful upload batch, if `user_settings.active_shop_site` IS NULL, set it to the `shop_site` with the most rows in that batch.
- Never overwrite a non-NULL value.

If you reach this stage and that behavior is missing from the Stage 2 worker, add it now and verify with a regression test.

## Frontend

### Global shop switcher in the header

A dropdown (shadcn `Select`) sitting in the top bar of `/dashboard/*` layout:

- Populated from `available_shop_sites`.
- Selected value reflects `active_shop_site`.
- Changing it calls `PATCH /api/settings` and invalidates relevant React Query caches so every downstream list refreshes.
- If the user has zero shops yet, the switcher is replaced with a hint: "Upload an order file to start."

This switcher is the seller's **primary** way to scope the view to a particular shop. Filters inside the repeat-order list (Stage 4) should respect it implicitly — they do not also need a `shop_site` dropdown.

### `/dashboard/settings` page

A single page with four sections (each its own card):

1. **Active Shop**
   - Same `Select` as the header switcher, but in full-width form.

2. **Repeat Grain**
   - Radio group with three options:
     - `asin` — Exact variant (default, strict)
     - `spu` — Same parent product / SPU (medium)
     - `product_name` — Same product name (loose)
   - One-sentence explanation under each option.
   - Below the radios: a small live preview box that calls a helper endpoint (see below) to show "X repeat buyers, Y repeat orders" for the chosen grain.

3. **Excluded Order Types**
   - Multi-select of `available_order_types`.
   - Help text: "Orders of these types will be hidden from the repeat-orders list. Typical exclusions: cancellations, refunds, gift returns."

4. **Timezone**
   - Searchable combobox of common IANA timezones (you can hard-code a list of ~50 common ones; do not enumerate the full database).
   - All timestamps in the app render in this timezone.

### Helper endpoint for the live preview

`GET /api/repeat-orders/preview?grain=asin`

Returns:
```json
{ "repeat_buyer_count": 432, "repeat_order_count": 1518 }
```

Computed against the active shop site and current excluded order types.

## Tests

`backend/tests/test_settings.py`:
- Defaults are correct for a brand-new user.
- `available_shop_sites` reflects the user's actual orders, not other users'.
- Setting `active_shop_site` to a value not in `available_shop_sites` is rejected.
- Setting an invalid timezone is rejected.
- Setting `repeat_grain` to a non-enum value is rejected.
- The first-upload hook sets `active_shop_site` only when it was previously NULL.

## Acceptance checks

1. Brand-new user (no uploads) sees the settings page with empty shop list and a hint message.
2. After the first upload, the global shop switcher shows that shop selected.
3. Switching grain between asin / spu / product_name updates the preview counts.
4. Excluding `退货` (if present) causes the count to drop.
5. Changing timezone updates the formatting of recent uploads' timestamps on `/dashboard/uploads`.

## Out of scope

- No per-shop different settings (one set of settings governs all shops; only `active_shop_site` is which-shop-am-I-looking-at).
- No team / multi-user settings.
- No notification preferences.
