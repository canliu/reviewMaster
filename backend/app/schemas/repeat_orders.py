from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class RepeatPreviewOut(BaseModel):
    repeat_buyer_count: int
    repeat_order_count: int


class RepeatOrderSummary(BaseModel):
    total_repeat_orders: int
    total_repeat_buyers: int
    total_repeat_products: int
    in_review_window: int
    already_requested: int


class ActiveReview(BaseModel):
    id: UUID
    status: Literal["sent", "pending"]
    method: Literal["manual", "link", "api"]
    requested_at: datetime


class RepeatOrderItem(BaseModel):
    order_uuid: UUID
    order_id: str
    shop_site: str
    asin: str | None
    spu: str | None
    product_name: str | None
    product_title_short: str | None
    order_type: str | None
    buyer_email: str | None
    buyer_key: str
    order_time_utc: datetime | None
    estimated_delivery_utc: datetime | None
    item_price: float | None
    currency: str | None
    quantity: int | None
    ship_city: str | None
    ship_state: str | None
    ship_country: str | None
    purchase_index: int
    total_purchases: int
    review_request: ActiveReview | None
    can_request_review: bool
    can_request_reason: str | None


class RepeatOrderList(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[RepeatOrderItem]


class BuyerHistoryOrder(BaseModel):
    order_id: str
    asin: str | None
    product_name: str | None
    order_time_utc: datetime | None
    item_price: float | None
    quantity: int | None
    review_request_status: Literal["sent", "pending"] | None


class BuyerHistory(BaseModel):
    buyer_key: str
    buyer_email: str | None
    total_orders_all_products: int
    orders_returned: int
    has_more: bool
    orders: list[BuyerHistoryOrder]


class RepeatOrderDetail(BaseModel):
    order: RepeatOrderItem
    buyer_history: BuyerHistory
