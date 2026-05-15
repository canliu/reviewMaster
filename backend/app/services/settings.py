"""Read/write user settings.

`users.timezone` and `user_settings.*` are kept in two tables (because
`users.timezone` predates settings as a concept). The API surfaces them as
one logical object; this service layer is the seam.
"""
from __future__ import annotations

import zoneinfo
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models.order import Order
from app.models.user import User
from app.models.user_settings import UserSettings

VALID_GRAINS = {"asin", "spu", "product_name"}


async def get_settings(db: AsyncSession, user: User) -> dict[str, Any]:
    settings_row = await _ensure_settings_row(db, user.id)
    available_shops = await _available_shop_sites(db, user.id)
    available_types = await _available_order_types(db, user.id)
    return {
        "active_shop_site": settings_row.active_shop_site,
        "repeat_grain": settings_row.repeat_grain,
        "excluded_order_types": list(settings_row.excluded_order_types or []),
        "timezone": user.timezone,
        "available_shop_sites": available_shops,
        "available_order_types": available_types,
        "available_scopes": _build_scopes(available_shops),
    }


def _build_scopes(available_shops: list[str]) -> list[dict[str, str]]:
    """Build the scope list shown in the shop switcher.

    Each real shop_site is one scope. Marketplaces with 2+ shops also get
    an `all:<MARKET>` virtual scope at the top (cross-shop within that
    marketplace).
    """
    from collections import defaultdict

    by_market: dict[str, list[str]] = defaultdict(list)
    for shop in available_shops:
        if ":" in shop:
            market = shop.rsplit(":", 1)[1].strip().upper()
            if market:
                by_market[market].append(shop)

    scopes: list[dict[str, str]] = []
    for market in sorted(by_market):
        shops = by_market[market]
        if len(shops) >= 2:
            scopes.append(
                {
                    "value": f"all:{market}",
                    "label": f"All shops · {market} ({len(shops)})",
                    "type": "marketplace",
                    "marketplace": market,
                }
            )
        for shop in sorted(shops):
            scopes.append(
                {"value": shop, "label": shop, "type": "shop", "marketplace": market}
            )
    return scopes


async def update_settings(
    db: AsyncSession, user: User, patch: dict[str, Any]
) -> dict[str, Any]:
    """Apply only the keys present in `patch`. Validates each before writing."""
    settings_row = await _ensure_settings_row(db, user.id)
    available_shops = await _available_shop_sites(db, user.id)
    available_types = await _available_order_types(db, user.id)

    if "active_shop_site" in patch:
        value = patch["active_shop_site"]
        valid_values = {s["value"] for s in _build_scopes(available_shops)}
        if value is not None and value not in valid_values:
            raise APIError(
                422,
                "INVALID_SHOP_SITE",
                f"'{value}' is not one of your scopes.",
            )
        settings_row.active_shop_site = value

    if "repeat_grain" in patch:
        value = patch["repeat_grain"]
        if value not in VALID_GRAINS:
            raise APIError(
                422,
                "INVALID_REPEAT_GRAIN",
                f"repeat_grain must be one of {sorted(VALID_GRAINS)}.",
            )
        settings_row.repeat_grain = value

    if "excluded_order_types" in patch:
        value = patch["excluded_order_types"]
        if not isinstance(value, list):
            raise APIError(
                422, "INVALID_EXCLUDED_TYPES", "excluded_order_types must be a list."
            )
        # Permissive: allow types not currently in the user's orders, since
        # an upload could add them later. The prompt requires they exist now,
        # so enforce the strict version.
        unknown = [t for t in value if t not in available_types]
        if unknown:
            raise APIError(
                422,
                "INVALID_EXCLUDED_TYPES",
                f"Unknown order types: {unknown}",
            )
        settings_row.excluded_order_types = value

    if "timezone" in patch:
        tz = patch["timezone"]
        if not isinstance(tz, str):
            raise APIError(422, "INVALID_TIMEZONE", "timezone must be a string.")
        try:
            zoneinfo.ZoneInfo(tz)
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                422, "INVALID_TIMEZONE", f"'{tz}' is not a valid IANA timezone."
            ) from exc
        user.timezone = tz

    await db.commit()
    await db.refresh(settings_row)
    await db.refresh(user)
    return await get_settings(db, user)


async def _ensure_settings_row(db: AsyncSession, user_id: UUID) -> UserSettings:
    """Belt-and-suspenders: register/upload already create this row, but a
    pre-existing user from before user_settings was added would lack one."""
    row = await db.get(UserSettings, user_id)
    if row is not None:
        return row
    row = UserSettings(user_id=user_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _available_shop_sites(db: AsyncSession, user_id: UUID) -> list[str]:
    rows = await db.execute(
        select(Order.shop_site)
        .where(Order.user_id == user_id)
        .distinct()
        .order_by(Order.shop_site)
    )
    return [r[0] for r in rows.all() if r[0] is not None]


async def _available_order_types(db: AsyncSession, user_id: UUID) -> list[str]:
    rows = await db.execute(
        select(Order.order_type)
        .where(Order.user_id == user_id)
        .where(Order.order_type.is_not(None))
        .distinct()
        .order_by(Order.order_type)
    )
    return [r[0] for r in rows.all() if r[0] is not None]
