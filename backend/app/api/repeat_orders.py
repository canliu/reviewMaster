from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import APIError
from app.models.buyer_product_stat import BuyerProductStat
from app.models.order import Order
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.repeat_orders import RepeatPreviewOut

router = APIRouter(prefix="/api/repeat-orders", tags=["repeat-orders"])

_VALID_GRAINS = {"asin", "spu", "product_name"}


@router.get("/preview", response_model=RepeatPreviewOut)
async def preview(
    grain: str = Query(..., description="asin | spu | product_name"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepeatPreviewOut:
    """Return repeat-buyer / repeat-order counts for the active shop and
    current excluded-types filter, at the requested grain.

    A "repeat" group is one with order_count >= 2 in buyer_product_stats.
    The order count is then refined by subtracting orders whose `order_type`
    is in the user's `excluded_order_types`.
    """
    if grain not in _VALID_GRAINS:
        raise APIError(
            422, "INVALID_GRAIN", f"grain must be one of {sorted(_VALID_GRAINS)}."
        )

    settings_row = await db.get(UserSettings, user.id)
    if settings_row is None or settings_row.active_shop_site is None:
        return RepeatPreviewOut(repeat_buyer_count=0, repeat_order_count=0)
    shop = settings_row.active_shop_site
    excluded = list(settings_row.excluded_order_types or [])

    # Pull repeat groups first (cheap, indexed in stats table).
    repeat_groups = (
        await db.execute(
            select(
                BuyerProductStat.buyer_key,
                BuyerProductStat.group_value,
            )
            .where(BuyerProductStat.user_id == user.id)
            .where(BuyerProductStat.shop_site == shop)
            .where(BuyerProductStat.grain == grain)
            .where(BuyerProductStat.order_count >= 2)
        )
    ).all()

    if not repeat_groups:
        return RepeatPreviewOut(repeat_buyer_count=0, repeat_order_count=0)

    # Count actual orders that fall in these groups and are not excluded.
    grain_col = {"asin": Order.asin, "spu": Order.spu, "product_name": Order.product_name}[
        grain
    ]
    pairs = [(b, g) for b, g in repeat_groups]
    # Build a row-value IN clause: WHERE (buyer_key, group_value) IN (...).
    from sqlalchemy import tuple_

    base = (
        select(func.count(Order.id), func.count(func.distinct(Order.buyer_key)))
        .where(Order.user_id == user.id)
        .where(Order.shop_site == shop)
        .where(tuple_(Order.buyer_key, grain_col).in_(pairs))
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
