from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("user_id", "order_id", name="orders_user_id_order_id_key"),
        Index(
            "orders_user_shop_buyer_asin_idx",
            "user_id",
            "shop_site",
            "buyer_key",
            "asin",
        ),
        Index(
            "orders_user_shop_buyer_spu_idx",
            "user_id",
            "shop_site",
            "buyer_key",
            "spu",
        ),
        Index("orders_user_eta_idx", "user_id", "estimated_delivery_utc"),
        Index("orders_user_shop_idx", "user_id", "shop_site"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[str] = mapped_column(String, nullable=False)
    shop_site: Mapped[str] = mapped_column(String, nullable=False)

    asin: Mapped[str | None] = mapped_column(String, nullable=True)
    msku: Mapped[str | None] = mapped_column(String, nullable=True)
    sku: Mapped[str | None] = mapped_column(String, nullable=True)
    spu: Mapped[str | None] = mapped_column(String, nullable=True)
    product_name: Mapped[str | None] = mapped_column(String, nullable=True)
    product_title: Mapped[str | None] = mapped_column(String, nullable=True)
    parent_product_name: Mapped[str | None] = mapped_column(String, nullable=True)
    order_type: Mapped[str | None] = mapped_column(String, nullable=True)

    buyer_email: Mapped[str | None] = mapped_column(String, nullable=True)
    buyer_key: Mapped[str] = mapped_column(String, nullable=False)

    order_time_utc: Mapped[datetime | None] = mapped_column(nullable=True)
    ship_time_utc: Mapped[datetime | None] = mapped_column(nullable=True)
    estimated_delivery_utc: Mapped[datetime | None] = mapped_column(nullable=True)

    item_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ship_city: Mapped[str | None] = mapped_column(String, nullable=True)
    ship_state: Mapped[str | None] = mapped_column(String, nullable=True)
    ship_country: Mapped[str | None] = mapped_column(String, nullable=True)

    tracking_number: Mapped[str | None] = mapped_column(String, nullable=True)
    carrier: Mapped[str | None] = mapped_column(String, nullable=True)

    raw_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
