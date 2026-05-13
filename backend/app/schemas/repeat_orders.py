from __future__ import annotations

from pydantic import BaseModel


class RepeatPreviewOut(BaseModel):
    repeat_buyer_count: int
    repeat_order_count: int
