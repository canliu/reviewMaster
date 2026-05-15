from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class SellerCredential(Base):
    """Encrypted SP-API credentials, one row per (user, shop_site).

    Sellers commonly manage one Amazon developer app per marketplace, so we
    key on the user's shop_site (the same string surfaced in the shop
    switcher) rather than a single credential set per user.
    """

    __tablename__ = "seller_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    shop_site: Mapped[str] = mapped_column(String, primary_key=True)
    dek_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    lwa_client_id: Mapped[str] = mapped_column(String, nullable=False)
    lwa_client_secret_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    selling_partner_id: Mapped[str] = mapped_column(String, nullable=False)
    marketplace_id: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
