from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UploadEnqueued(BaseModel):
    batch_id: UUID
    status: str


class UploadBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    file_size_bytes: int
    total_rows: int
    new_rows: int
    updated_rows: int
    duplicate_rows: int
    error_rows: int
    progress: int
    status: str
    error_detail: dict[str, Any] | None = None
    started_at: datetime
    completed_at: datetime | None = None


class UploadListOut(BaseModel):
    items: list[UploadBatchOut]
    total: int
    page: int
    page_size: int
