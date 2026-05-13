from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateRequestIn(BaseModel):
    order_uuids: list[UUID] = Field(min_length=1)
    method: Literal["manual", "link"]
    note: str | None = Field(default=None, max_length=500)


class CreatedItem(BaseModel):
    id: UUID
    order_uuid: UUID
    method: Literal["manual", "link", "api"]
    status: Literal["pending", "sent", "failed"]
    redirect_url: str | None = None


class SkippedItem(BaseModel):
    order_uuid: UUID
    reason: str


class ErrorItem(BaseModel):
    order_uuid: UUID
    code: str
    reason: str


class CreateRequestOut(BaseModel):
    created: list[CreatedItem]
    skipped: list[SkippedItem]
    errors: list[ErrorItem]


class ReviewRequestListItem(BaseModel):
    id: UUID
    order_uuid: UUID
    method: Literal["manual", "link", "api"]
    status: Literal["pending", "sent", "failed"]
    requested_at: datetime
    api_response: dict[str, Any] | None = None
    # Joined order summary
    order_id: str
    shop_site: str
    asin: str | None
    product_name: str | None
    buyer_email: str | None
    notes_count: int


class ReviewRequestListOut(BaseModel):
    items: list[ReviewRequestListItem]
    total: int
    page: int
    page_size: int


class NoteOut(BaseModel):
    id: UUID
    order_uuid: UUID
    review_request_id: UUID | None
    note: str
    kind: Literal["user", "system"]
    created_at: datetime


class ReviewRequestDetail(BaseModel):
    request: ReviewRequestListItem
    notes: list[NoteOut]
