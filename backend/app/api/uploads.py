from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import APIError
from app.models.upload_batch import UploadBatch
from app.models.user import User
from app.schemas.upload import UploadBatchOut, UploadEnqueued, UploadListOut
from app.services.uploads import receive_upload

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("", response_model=UploadEnqueued, status_code=status.HTTP_202_ACCEPTED)
async def create_upload(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadEnqueued:
    batch = await receive_upload(db, user.id, file)
    return UploadEnqueued(batch_id=batch.id, status=batch.status)


@router.get("", response_model=UploadListOut)
async def list_uploads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadListOut:
    total = (
        await db.execute(
            select(func.count(UploadBatch.id)).where(UploadBatch.user_id == user.id)
        )
    ).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            select(UploadBatch)
            .where(UploadBatch.user_id == user.id)
            .order_by(UploadBatch.started_at.desc())
            .offset(offset)
            .limit(page_size)
        )
    ).scalars().all()
    return UploadListOut(
        items=[UploadBatchOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{batch_id}", response_model=UploadBatchOut)
async def get_upload(
    batch_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadBatchOut:
    batch = (
        await db.execute(
            select(UploadBatch)
            .where(UploadBatch.id == batch_id)
            .where(UploadBatch.user_id == user.id)
        )
    ).scalar_one_or_none()
    if batch is None:
        raise APIError(404, "NOT_FOUND", "Upload batch not found.")
    return UploadBatchOut.model_validate(batch)
