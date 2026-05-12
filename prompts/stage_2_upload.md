# Stage 2 — Excel Upload, Parsing, and Ingestion

> Builds on Stages 0–1. This is the heaviest stage of the MVP. Take care with idempotency, performance, and crash recovery.

## Goal

A logged-in seller can upload an Amazon order export (.xlsx), have it parsed asynchronously, and see a per-row ingestion report (new / updated / duplicate / error). Re-uploading the same file produces zero new rows. The buyer-product statistics table is refreshed automatically.

## Source file shape

The seller uploads a single .xlsx with one sheet named `配送信息` (Chinese for "shipping info"). It has 43 columns; the ones we actually consume are listed below, with their target field in the `orders` table.

| Excel column (Chinese, exact) | DB field |
|---|---|
| 店铺/站点 | shop_site |
| 订单编号 | order_id |
| ASIN | asin |
| MSKU | msku |
| SKU | sku |
| SPU | spu |
| 产品名称 | product_name |
| 父产品名称 | parent_product_name |
| 商品标题 | product_title |
| 订单类型 | order_type |
| 买家邮箱 | buyer_email |
| 订购时间（零时区） | order_time_utc |
| 发货时间（零时区） | ship_time_utc |
| 预计到达时间（零时区） | estimated_delivery_utc |
| 商品售价 | item_price |
| 币种 | currency |
| 发货数量 | quantity |
| 收货城市 | ship_city |
| 收货地区 | ship_state |
| 收货国家/地区 | ship_country |
| 追踪号码 | tracking_number |
| 承运人 | carrier |

The **full original row** (all 43 columns, keys as the original Chinese headers) is stored in `raw_json`. Do not drop any column.

Notes about the Chinese column names:
- Several headers use full-width parentheses `（）`, not ASCII `()`. Match exact strings.
- Trim whitespace from headers before matching, in case the export has trailing spaces.

## The `buyer_key` rule

For each row, compute a `buyer_key` at ingestion time. This is the canonical buyer identifier used for repeat detection.

- If `buyer_email` is present and non-empty: `buyer_key = "email:" + lowercase(buyer_email)`
- Otherwise: `buyer_key = "addr:" + sha256(shop_site + "|" + country + "|" + state + "|" + city)` (all lowercased and stripped; missing values become empty string)
- Store the resulting string in `orders.buyer_key`.

Document this rule in a docstring on the service function that computes it.

## Required columns and validation

Before processing any row, validate that the sheet contains these required columns (after header trim):

- 店铺/站点, 订单编号, 订购时间（零时区）, 买家邮箱 or fallback address columns (城市/地区/国家)

If a required column is missing, mark the whole batch as `failed`, write the missing-columns list into `error_detail`, and do not insert any orders.

## Endpoints

### `POST /api/uploads`
- Multipart form, field `file`.
- Accept only `.xlsx`. Max 50 MB.
- Save to `/tmp/uploads/{batch_id}.xlsx`.
- Create an `upload_batches` row with `status='processing'`, `progress=0`, `total_rows=NULL` (until parsing has counted them).
- Enqueue an RQ job `process_upload(batch_id, user_id, file_path)`.
- Return `{batch_id, status: "processing"}` immediately (HTTP 202).

### `GET /api/uploads`
- Lists the current user's upload history, newest first, paginated (default 20).
- Returns: filename, total/new/updated/duplicate/error rows, status, started_at, completed_at.

### `GET /api/uploads/{batch_id}`
- Returns the full record including `error_detail` and `progress` (so the frontend can show a progress bar).

## Worker job: `process_upload`

Steps the worker must perform, in order:

1. Load the file with `pandas.read_excel`, sheet `配送信息`. Catch any failure → mark batch `failed`, store the exception in `error_detail`.
2. Validate required columns. Bail if any are missing.
3. Set `total_rows` on the batch.
4. Process in chunks of 500 rows. **Each chunk runs in its own database transaction.** Committing per chunk means the `progress` field reflects real on-disk state, and a worker crash mid-batch leaves the already-processed rows safely persisted (subsequent retries from the user will see them as duplicates, which is correct). After each chunk:
   - Build a list of order dicts for that chunk.
   - For each row, derive `buyer_key`, parse timestamps (already UTC), clean numbers (strip currency symbols, commas).
   - Skip rows with empty `order_id` → count as error_rows with reason `"missing order_id"`.
   - Skip rows with item_price that won't parse → error_rows with reason `"unparseable price"`.
   - Use a PostgreSQL `INSERT ... ON CONFLICT (user_id, order_id) DO UPDATE SET ...` (with `RETURNING xmax = 0` to distinguish new vs updated).
   - Within the same upload, if the same `order_id` appears twice, the second occurrence counts as `duplicate_rows` and overwrites.
   - Commit the transaction, then update `batch.progress` (in its own short transaction).
5. After all rows are processed, collect the set of `(shop_site, buyer_key, grain, group_value)` tuples affected by this batch, where grain is each of `'asin'`, `'spu'`, `'product_name'` and group_value is the corresponding field. Rows missing the grouping field for a given grain are skipped for that grain.
6. Refresh `buyer_product_stats` for those tuples with a single SQL upsert:

   ```sql
   INSERT INTO buyer_product_stats (user_id, shop_site, buyer_key, grain, group_value,
                                    order_count, first_order_at, last_order_at, total_amount, updated_at)
   SELECT user_id, shop_site, buyer_key, :grain AS grain, <grouping_col> AS group_value,
          COUNT(*), MIN(order_time_utc), MAX(order_time_utc),
          COALESCE(SUM(item_price * quantity), 0), NOW()
   FROM orders
   WHERE user_id = :uid
     AND (shop_site, buyer_key, <grouping_col>) IN (:affected_tuples)
   GROUP BY user_id, shop_site, buyer_key, <grouping_col>
   ON CONFLICT (user_id, shop_site, buyer_key, grain, group_value)
   DO UPDATE SET order_count = EXCLUDED.order_count,
                 first_order_at = EXCLUDED.first_order_at,
                 last_order_at = EXCLUDED.last_order_at,
                 total_amount = EXCLUDED.total_amount,
                 updated_at = NOW();
   ```

   Run this once per grain.

7. Mark the batch `completed`, set `completed_at`, delete the temp file.
8. **First-upload hook**: in the same transaction, check if the user's `user_settings.active_shop_site` is NULL. If so, set it to the `shop_site` value with the most rows in this batch. This lets fresh users skip a manual shop-picker step. Do **not** overwrite a non-null setting.
9. On any unhandled exception: mark `failed`, write `error_detail`, leave the temp file for debugging.

## Crash recovery

If the worker crashes mid-batch and the process restarts, leave the old `processing` batch alone — a separate sweeper (run on backend startup, see below) will mark any `processing` batch older than 1 hour as `failed` with `error_detail = {"reason": "worker timeout / crash"}`. Do not attempt to resume mid-batch; the seller should re-upload.

Add the sweeper as an on-startup task in `main.py`.

## Frontend

`/dashboard/uploads` page:

1. **Upload card** at the top:
   - Drag-and-drop zone or click-to-select.
   - Accepts only `.xlsx`.
   - On selection, POST the file; on response, start polling `GET /api/uploads/{batch_id}` every 2 seconds.
   - Show a progress bar driven by `progress / total_rows`.
   - On completion, show a toast: `"New: X, Updated: Y, Duplicates: Z, Errors: W"`.
   - On failure, show the `error_detail.reason` in an error alert.

2. **History table** below:
   - Columns: Filename, Status (badge), Total, New, Updated, Duplicates, Errors, Started At, Completed At.
   - Newest first. Pagination 20 per page.
   - Click a row to open a side panel showing `error_detail` if any.

## Performance target

- Throughput target: **≥ 400 rows/second sustained** for the chunked ingestion (measured worker-side, excluding HTTP round-trip).
- On a 30,000-row file this works out to roughly 75 seconds of worker time; the API should respond in well under a second since work is async.
- Re-uploading the same 30,000-row file should produce 30,000 duplicates and finish faster than a fresh ingest because there are no row inserts — only conflict checks.

## Tests

`backend/tests/test_upload.py`:
- A 10-row fixture .xlsx at `backend/tests/fixtures/sample_orders.xlsx` exercises the happy path; counts match. The verify script for this stage checks for this exact path — do not improvise a different name.
- Missing a required column → batch ends `failed`, no orders inserted.
- A row with empty `order_id` → counted in `error_rows`, others inserted.
- Re-uploading the same fixture → all rows counted as duplicate, `orders` table unchanged in shape.
- `buyer_key` correctly falls back to address hash when email is missing.
- `buyer_product_stats` reflects the right `order_count` for the three grains.

## Acceptance checks

1. Upload the real 30,000-row file. Finish within target. Counts match expectations.
2. Upload it again. New rows = 0, duplicates ≈ 30,000.
3. `SELECT COUNT(*) FROM buyer_product_stats WHERE order_count >= 2 AND grain='asin';` returns a sensible number.
4. Pick a row in `orders` and confirm `raw_json` contains every original column with its Chinese key.
5. Tamper with the file (rename a required column) and confirm the batch fails cleanly without partial inserts.
6. Kill the worker mid-upload, wait 1 hour (or temporarily lower the sweeper threshold for testing), restart backend → the stale batch is marked failed.

## Out of scope

- No retry-from-progress (intentional — see Crash recovery).
- No CSV uploads (only .xlsx).
- No multi-sheet workbooks.
- No file storage in S3 (local /tmp is fine for MVP).
