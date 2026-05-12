from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class SellerCredential(Base):
    """Encrypted SP-API credentials. Created here, populated in Stage 6."""

    __tablename__ = "seller_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    dek_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    lwa_client_id: Mapped[str] = mapped_column(String, nullable=False)
    lwa_client_secret_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    selling_partner_id: Mapped[str] = mapped_column(String, nullable=False)
    marketplace_id: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
