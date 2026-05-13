from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class BuyerProductStat(Base):
    __tablename__ = "buyer_product_stats"
    __table_args__ = (
        CheckConstraint(
            "grain IN ('asin', 'spu', 'product_name')",
            name="buyer_product_stats_grain_check",
        ),
        Index(
            "buyer_stats_user_shop_grain_count_idx",
            "user_id",
            "shop_site",
            "grain",
            "order_count",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    shop_site: Mapped[str] = mapped_column(String, primary_key=True)
    buyer_key: Mapped[str] = mapped_column(String, primary_key=True)
    grain: Mapped[str] = mapped_column(String, primary_key=True)
    group_value: Mapped[str] = mapped_column(String, primary_key=True)

    order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
