from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsOut(BaseModel):
    active_shop_site: str | None
    repeat_grain: str
    excluded_order_types: list[str]
    timezone: str

    # Computed from the user's own orders. Used by the frontend to populate
    # the shop switcher and the excluded-types multi-select.
    available_shop_sites: list[str]
    available_order_types: list[str]


class SettingsPatch(BaseModel):
    # Default of None means "not provided" only when we use
    # `model_dump(exclude_unset=True)` in the service — a client that
    # explicitly sends `null` (e.g. to clear active_shop_site) is honored.
    active_shop_site: str | None = Field(default=None)
    repeat_grain: str | None = Field(default=None)
    excluded_order_types: list[str] | None = Field(default=None)
    timezone: str | None = Field(default=None)
