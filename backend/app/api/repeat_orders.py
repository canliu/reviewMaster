from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
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
