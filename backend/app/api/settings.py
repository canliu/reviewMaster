from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.settings import SettingsOut, SettingsPatch
from app.services.settings import get_settings, update_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
async def read_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SettingsOut:
    return SettingsOut(**(await get_settings(db, user)))


@router.patch("", response_model=SettingsOut)
async def patch_settings(
    body: SettingsPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SettingsOut:
    # `exclude_unset=True` separates "client didn't send this field" (skip)
    # from "client explicitly sent null" (e.g. clear active_shop_site).
    return SettingsOut(
        **(await update_settings(db, user, body.model_dump(exclude_unset=True)))
    )
