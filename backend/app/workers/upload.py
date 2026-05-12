"""RQ job: ingest an uploaded .xlsx of Amazon orders.

Steps mirror stage_2_upload.md exactly:
  1. Load workbook (sheet ``配送信息``).
  2. Validate required columns; bail if missing.
  3. Process in 500-row chunks, each in its own transaction.
  4. Upsert into ``orders`` with ON CONFLICT (user_id, order_id) and
     RETURNING (xmax = 0) so we can count new vs updated rows.
  5. Refresh ``buyer_product_stats`` for the affected (shop, buyer, group)
     tuples across the three grains.
  6. Mark batch completed, run the first-upload hook, drop the temp file.
"""
from __future__ import annotations

import math
import os
import uuid
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.order import Order

from app.core.logger import get_logger
from app.models.upload_batch import UploadBatch
from app.models.user_settings import UserSettings
from app.services.buyer_key import derive_buyer_key
from app.services.stats_refresh import refresh_for_grain
from app.workers.db import SyncSessionLocal

logger = get_logger(__name__)

SHEET_NAME = "配送信息"
CHUNK_SIZE = 500
SUPPORTED_GRAINS = ("asin", "spu", "product_name")

# Excel-column → orders-column map. Headers in the .xlsx are matched after
# whitespace is stripped (some exports add trailing spaces).
COLUMN_MAP: dict[str, str] = {
    "店铺/站点": "shop_site",
    "订单编号": "order_id",
    "ASIN": "asin",
    "MSKU": "msku",
    "SKU": "sku",
    "SPU": "spu",
    "产品名称": "product_name",
    "父产品名称": "parent_product_name",
    "商品标题": "product_title",
    "订单类型": "order_type",
    "买家邮箱": "buyer_email",
    "订购时间（零时区）": "order_time_utc",
    "发货时间（零时区）": "ship_time_utc",
    "预计到达时间（零时区）": "estimated_delivery_utc",
    "商品售价": "item_price",
    "币种": "currency",
    "发货数量": "quantity",
    "收货城市": "ship_city",
    "收货地区": "ship_state",
    "收货国家/地区": "ship_country",
    "追踪号码": "tracking_number",
    "承运人": "carrier",
}

# A row needs these mapped columns to be processable. The buyer_email vs
# address-fallback is enforced separately (at least ONE of email or city must
# be present per row, not at column level).
REQUIRED_DB_COLUMNS = {"shop_site", "order_id", "order_time_utc"}


# ---------- public entrypoint ----------

def process_upload(batch_id: str, user_id: str, file_path: str) -> None:
    """RQ entrypoint. Always settles the batch status to ``completed`` or
    ``failed`` — never leaves it in ``processing``."""
    batch_uuid = UUID(batch_id)
    user_uuid = UUID(user_id)
    try:
        _do_process(batch_uuid, user_uuid, file_path)
    except Exception as exc:  # noqa: BLE001 — last-chance handler
        logger.exception("process_upload failed for batch %s", batch_id)
        _mark_failed(batch_uuid, {"reason": str(exc), "type": type(exc).__name__})
        raise


# ---------- core pipeline ----------

def _do_process(batch_id: UUID, user_id: UUID, file_path: str) -> None:
    try:
        df = pd.read_excel(file_path, sheet_name=SHEET_NAME, dtype=object)
    except Exception as exc:  # noqa: BLE001
        _mark_failed(batch_id, {"reason": f"failed to read xlsx: {exc}"})
        return

    # Trim header whitespace per the prompt.
    df.columns = [str(c).strip() for c in df.columns]

    # Build present-column → DB-field map.
    present_map = {excel: db for excel, db in COLUMN_MAP.items() if excel in df.columns}
    missing_db_cols = REQUIRED_DB_COLUMNS - set(present_map.values())
    if missing_db_cols:
        _mark_failed(
            batch_id,
            {"reason": "missing required columns", "missing": sorted(missing_db_cols)},
        )
        return

    total_rows = int(len(df))
    with SyncSessionLocal() as session:
        batch = session.get(UploadBatch, batch_id)
        if batch is None:
            return
        batch.total_rows = total_rows
        session.commit()

    counters = Counter()
    seen_in_batch: set[str] = set()
    affected: set[tuple[str, str, str | None, str | None, str | None]] = set()
    progress = 0
    raw_columns = list(df.columns)

    for start in range(0, total_rows, CHUNK_SIZE):
        end = min(start + CHUNK_SIZE, total_rows)
        chunk = df.iloc[start:end]
        chunk_rows: list[dict[str, Any]] = []
        chunk_affected: list[tuple[str, str, str | None, str | None, str | None]] = []

        for _idx, row in chunk.iterrows():
            built = _build_order_record(row, user_id, present_map, raw_columns)
            if isinstance(built, str):  # error reason
                counters["error_rows"] += 1
                continue

            order_id = built["order_id"]
            if order_id in seen_in_batch:
                counters["duplicate_rows"] += 1
            seen_in_batch.add(order_id)

            chunk_rows.append(built)
            chunk_affected.append(
                (
                    built["shop_site"],
                    built["buyer_key"],
                    built.get("asin"),
                    built.get("spu"),
                    built.get("product_name"),
                )
            )

        if chunk_rows:
            with SyncSessionLocal() as session:
                new_count, updated_count = _upsert_chunk(session, user_id, chunk_rows)
                # `new_count + updated_count` is the count of rows that made
                # it into the DB this chunk. A row whose order_id repeated
                # within the batch only reaches the DB once (last write wins)
                # but the original new/updated counter shouldn't double-count
                # it; the in-batch dup is already tallied above.
                counters["new_rows"] += new_count
                counters["updated_rows"] += updated_count
                session.commit()
            affected.update(chunk_affected)

        progress = end
        with SyncSessionLocal() as session:
            batch = session.get(UploadBatch, batch_id)
            if batch is not None:
                batch.progress = progress
                session.commit()

    # ---- stats refresh ----
    with SyncSessionLocal() as session:
        for grain in SUPPORTED_GRAINS:
            tuples: set[tuple[str, str, str]] = set()
            for (shop, bkey, asin, spu, pname) in affected:
                value = {"asin": asin, "spu": spu, "product_name": pname}[grain]
                if value:
                    tuples.add((shop, bkey, value))
            refresh_for_grain(session, user_id, grain, tuples)
        session.commit()

    # ---- finalize batch + first-upload hook ----
    with SyncSessionLocal() as session:
        batch = session.get(UploadBatch, batch_id)
        if batch is not None:
            batch.status = "completed"
            batch.new_rows = counters["new_rows"]
            batch.updated_rows = counters["updated_rows"]
            batch.duplicate_rows = counters["duplicate_rows"]
            batch.error_rows = counters["error_rows"]
            batch.progress = total_rows
            batch.completed_at = datetime.now(timezone.utc)

        # First-upload hook: only sets active_shop_site if it's still null.
        settings_row = session.get(UserSettings, user_id)
        if settings_row is not None and settings_row.active_shop_site is None:
            top_shop = _modal_shop(session, user_id)
            if top_shop:
                settings_row.active_shop_site = top_shop

        session.commit()

    # Best-effort temp-file cleanup. Failure here is logged but doesn't fail
    # the batch (it's already committed completed).
    try:
        os.remove(file_path)
    except OSError:
        logger.warning("could not delete temp file %s", file_path)


# ---------- helpers ----------

def _build_order_record(
    row: pd.Series,
    user_id: UUID,
    present_map: dict[str, str],
    raw_columns: list[str],
) -> dict[str, Any] | str:
    """Turn one xlsx row into a dict ready for the orders upsert.

    Returns a string error reason if the row should be tallied as an
    error_row instead of inserted.
    """
    fields: dict[str, Any] = {}
    for excel_col, db_col in present_map.items():
        value = row.get(excel_col)
        if value is None or (isinstance(value, float) and math.isnan(value)):
            fields[db_col] = None
        else:
            fields[db_col] = value

    order_id = fields.get("order_id")
    if order_id is None or str(order_id).strip() == "":
        return "missing order_id"
    fields["order_id"] = str(order_id).strip()

    fields["shop_site"] = str(fields.get("shop_site") or "").strip()
    if not fields["shop_site"]:
        return "missing shop_site"

    # Normalize known fields
    for str_col in (
        "asin", "msku", "sku", "spu",
        "product_name", "product_title", "parent_product_name",
        "order_type", "buyer_email", "currency",
        "ship_city", "ship_state", "ship_country",
        "tracking_number", "carrier",
    ):
        if fields.get(str_col) is not None:
            fields[str_col] = str(fields[str_col]).strip() or None

    for ts_col in ("order_time_utc", "ship_time_utc", "estimated_delivery_utc"):
        fields[ts_col] = _parse_timestamp(fields.get(ts_col))

    price_raw = fields.get("item_price")
    if price_raw is None or (isinstance(price_raw, float) and math.isnan(price_raw)):
        fields["item_price"] = None
    else:
        try:
            cleaned = str(price_raw).strip().replace(",", "")
            # Strip leading currency symbols / letters
            cleaned = cleaned.lstrip("$€¥£").strip()
            fields["item_price"] = Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return "unparseable price"

    qty_raw = fields.get("quantity")
    if qty_raw is None or (isinstance(qty_raw, float) and math.isnan(qty_raw)):
        fields["quantity"] = None
    else:
        try:
            fields["quantity"] = int(float(qty_raw))
        except (TypeError, ValueError):
            fields["quantity"] = None

    fields["buyer_key"] = derive_buyer_key(
        fields.get("buyer_email"),
        fields.get("shop_site"),
        fields.get("ship_country"),
        fields.get("ship_state"),
        fields.get("ship_city"),
    )

    fields["id"] = uuid.uuid4()
    fields["user_id"] = user_id

    # Preserve the full original row, keys as the original Chinese headers.
    raw = {}
    for col in raw_columns:
        val = row.get(col)
        if isinstance(val, pd.Timestamp):
            raw[col] = val.isoformat()
        elif isinstance(val, (datetime,)):
            raw[col] = val.isoformat()
        elif isinstance(val, float) and math.isnan(val):
            raw[col] = None
        elif isinstance(val, Decimal):
            raw[col] = str(val)
        else:
            raw[col] = val
    # SQLAlchemy JSONB serializes a dict; previous code passed a JSON string
    # because we were going through text() with CAST. Now we use pg_insert(),
    # so let the column adapter do the encoding.
    fields["raw_json"] = raw
    return fields


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, pd.Timestamp):
        ts = value.to_pydatetime()
    elif isinstance(value, datetime):
        ts = value
    else:
        try:
            ts = pd.to_datetime(value).to_pydatetime()
        except (ValueError, TypeError):
            return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


_UPDATE_ON_CONFLICT_COLS = (
    "shop_site", "asin", "msku", "sku", "spu",
    "product_name", "product_title", "parent_product_name", "order_type",
    "buyer_email", "buyer_key",
    "order_time_utc", "ship_time_utc", "estimated_delivery_utc",
    "item_price", "currency", "quantity",
    "ship_city", "ship_state", "ship_country",
    "tracking_number", "carrier",
    "raw_json",
)


def _upsert_chunk(
    session: Session, user_id: UUID, rows: list[dict[str, Any]]
) -> tuple[int, int]:
    """Bulk upsert with conflict counting. Two round-trips per chunk:

      1. SELECT to learn which order_ids already exist for this user.
      2. One multi-row INSERT ... ON CONFLICT DO UPDATE.

    Returns ``(new_count, updated_count)``. The earlier implementation did
    one round-trip per row to capture ``RETURNING (xmax = 0)``, which
    crawled on 30k-row uploads.
    """
    if not rows:
        return 0, 0

    order_ids = [r["order_id"] for r in rows]
    existing = set(
        session.scalars(
            select(Order.order_id)
            .where(Order.user_id == user_id)
            .where(Order.order_id.in_(order_ids))
        ).all()
    )

    stmt = pg_insert(Order).values(rows)
    update_map = {col: stmt.excluded[col] for col in _UPDATE_ON_CONFLICT_COLS}
    update_map["updated_at"] = text("NOW()")
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "order_id"],
        set_=update_map,
    )
    session.execute(stmt)

    new_count = sum(1 for r in rows if r["order_id"] not in existing)
    updated_count = len(rows) - new_count
    return new_count, updated_count


def _modal_shop(session: Session, user_id: UUID) -> str | None:
    """Return the shop_site with the most rows for this user, or None."""
    sql = text(
        "SELECT shop_site, COUNT(*) AS n FROM orders "
        "WHERE user_id = :uid GROUP BY shop_site ORDER BY n DESC LIMIT 1"
    )
    row = session.execute(sql, {"uid": user_id}).first()
    return row.shop_site if row else None


def _mark_failed(batch_id: UUID, detail: dict[str, Any]) -> None:
    with SyncSessionLocal() as session:
        batch = session.get(UploadBatch, batch_id)
        if batch is None:
            return
        batch.status = "failed"
        batch.error_detail = detail
        batch.completed_at = datetime.now(timezone.utc)
        session.commit()
