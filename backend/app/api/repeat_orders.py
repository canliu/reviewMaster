from __future__ import annotations

import csv
import io
from datetime import date
from typing import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import APIError
from app.models.buyer_product_stat import BuyerProductStat
from app.models.order import Order
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.repeat_orders import (
    RepeatOrderDetail,
    RepeatOrderList,
    RepeatOrderSummary,
    RepeatPreviewOut,
)
from app.services import repeat_orders as svc

router = APIRouter(prefix="/api/repeat-orders", tags=["repeat-orders"])

_VALID_GRAINS = {"asin", "spu", "product_name"}


# ---- existing preview (used by /settings live count) ----


@router.get("/preview", response_model=RepeatPreviewOut)
async def preview(
    grain: str = Query(..., description="asin | spu | product_name"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepeatPreviewOut:
    if grain not in _VALID_GRAINS:
        raise APIError(
            422, "INVALID_GRAIN", f"grain must be one of {sorted(_VALID_GRAINS)}."
        )

    settings_row = await db.get(UserSettings, user.id)
    if settings_row is None or settings_row.active_shop_site is None:
        return RepeatPreviewOut(repeat_buyer_count=0, repeat_order_count=0)
    shop = settings_row.active_shop_site
    excluded = list(settings_row.excluded_order_types or [])

    repeat_groups = (
        await db.execute(
            select(BuyerProductStat.buyer_key, BuyerProductStat.group_value)
            .where(BuyerProductStat.user_id == user.id)
            .where(BuyerProductStat.shop_site == shop)
            .where(BuyerProductStat.grain == grain)
            .where(BuyerProductStat.order_count >= 2)
        )
    ).all()
    if not repeat_groups:
        return RepeatPreviewOut(repeat_buyer_count=0, repeat_order_count=0)

    grain_col = {
        "asin": Order.asin,
        "spu": Order.spu,
        "product_name": Order.product_name,
    }[grain]
    base = (
        select(func.count(Order.id), func.count(func.distinct(Order.buyer_key)))
        .where(Order.user_id == user.id)
        .where(Order.shop_site == shop)
        .where(tuple_(Order.buyer_key, grain_col).in_([(b, g) for b, g in repeat_groups]))
    )
    if excluded:
        base = base.where(
            (Order.order_type.is_(None)) | (Order.order_type.notin_(excluded))
        )

    row = (await db.execute(base)).one()
    return RepeatPreviewOut(
        repeat_order_count=int(row[0] or 0),
        repeat_buyer_count=int(row[1] or 0),
    )


# ---- summary, list, detail (Stage 4 deliverables) ----


@router.get("/summary", response_model=RepeatOrderSummary)
async def get_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepeatOrderSummary:
    return RepeatOrderSummary(**(await svc.summary(db, user)))


@router.get("", response_model=RepeatOrderList)
async def list_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    asin: str | None = Query(None),
    product_search: str | None = Query(None, min_length=1),
    has_review_request: bool | None = Query(None),
    in_window: bool | None = Query(None),
    min_purchases: int = Query(svc.DEFAULT_MIN_PURCHASES, ge=1),
    sort: str = Query("last_order_desc"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepeatOrderList:
    return RepeatOrderList(
        **(
            await svc.list_orders(
                db,
                user,
                page=page,
                page_size=page_size,
                asin=asin,
                product_search=product_search,
                has_review_request=has_review_request,
                in_window=in_window,
                min_purchases=min_purchases,
                sort=sort,
            )
        )
    )


# CSV export — must come before the /{order_uuid} catch-all so FastAPI matches it first.
@router.get("/export.csv")
async def export_csv(
    asin: str | None = Query(None),
    product_search: str | None = Query(None, min_length=1),
    has_review_request: bool | None = Query(None),
    request_status: str | None = Query(
        None,
        description="Fine-grained: none|pending|sent|failed. Overrides has_review_request when set.",
    ),
    in_window: bool | None = Query(None),
    min_purchases: int = Query(svc.DEFAULT_MIN_PURCHASES, ge=1),
    sort: str = Query("last_order_desc"),
    shop_site_override: str | None = Query(
        None,
        description="Export a shop other than the active one (CSV exports only).",
    ),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    # Fresh session inside the generator — FastAPI closes request-scoped
    # sessions as soon as we return the StreamingResponse, but the generator
    # keeps emitting rows after.
    columns = [
        "order_id", "shop_site", "asin", "product_name", "buyer_email", "buyer_key",
        "ship_city", "ship_state", "ship_country",
        "order_time_utc", "estimated_delivery_utc",
        "item_price", "currency", "quantity",
        "purchase_index", "total_purchases",
        "request_method", "request_status",
        "can_request_review", "can_request_reason",
    ]
    user_id = user.id

    async def _rows() -> AsyncIterator[bytes]:
        from app.core.db import SessionLocal
        from app.models.user import User as UserModel

        async with SessionLocal() as session:
            current_user = (
                await session.execute(
                    select(UserModel).where(UserModel.id == user_id)
                )
            ).scalar_one()
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(columns)
            yield buf.getvalue().encode("utf-8")
            buf.seek(0)
            buf.truncate(0)

            page = 1
            page_size = 200
            while True:
                data = await svc.list_orders(
                    session, current_user,
                    page=page, page_size=page_size,
                    asin=asin, product_search=product_search,
                    has_review_request=has_review_request,
                    request_status=request_status,
                    in_window=in_window,
                    min_purchases=min_purchases, sort=sort,
                    shop_site_override=shop_site_override,
                )
                if not data["items"]:
                    break
                for it in data["items"]:
                    rr = it.get("review_request") or {}
                    writer.writerow([
                        it["order_id"], it["shop_site"], it.get("asin") or "",
                        it.get("product_name") or "", it.get("buyer_email") or "",
                        it["buyer_key"],
                        it.get("ship_city") or "", it.get("ship_state") or "",
                        it.get("ship_country") or "",
                        it["order_time_utc"].isoformat() if it.get("order_time_utc") else "",
                        it["estimated_delivery_utc"].isoformat() if it.get("estimated_delivery_utc") else "",
                        str(it["item_price"]) if it.get("item_price") is not None else "",
                        it.get("currency") or "",
                        it.get("quantity") if it.get("quantity") is not None else "",
                        it["purchase_index"], it["total_purchases"],
                        rr.get("method") or "", rr.get("status") or "",
                        "true" if it["can_request_review"] else "false",
                        it.get("can_request_reason") or "",
                    ])
                yield buf.getvalue().encode("utf-8")
                buf.seek(0)
                buf.truncate(0)
                if len(data["items"]) < page_size:
                    break
                page += 1

    # Include shop + status in the filename so multiple downloads don't
    # overwrite each other in the user's Downloads folder.
    shop_part = (shop_site_override or "all").replace(":", "-").replace("/", "-")
    status_part = request_status or "any"
    filename = f"repeat-orders-{shop_part}-{status_part}-{date.today().isoformat()}.csv"
    return StreamingResponse(
        _rows(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{order_uuid}", response_model=RepeatOrderDetail)
async def get_detail(
    order_uuid: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepeatOrderDetail:
    result = await svc.detail(db, user, order_uuid)
    if result is None:
        raise APIError(404, "NOT_FOUND", "Order not found.")
    return RepeatOrderDetail(**result)
