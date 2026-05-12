from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class UploadBatch(Base):
    __tablename__ = "upload_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'completed', 'failed')",
            name="upload_batches_status_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    new_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    duplicate_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    status: Mapped[str] = mapped_column(String, nullable=False)
    error_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
