"""Sweep stuck `processing` upload_batches.

Run once at backend startup. If a worker crashes mid-batch, its
upload_batches row sticks in `processing` forever; we mark anything older
than the threshold as `failed` so the UI doesn't lie.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.upload_batch import UploadBatch

logger = get_logger(__name__)

STALE_AFTER = timedelta(hours=1)


async def sweep_stale_batches(db: AsyncSession) -> int:
    cutoff = datetime.now(timezone.utc) - STALE_AFTER
    stmt = (
        update(UploadBatch)
        .where(UploadBatch.status == "processing")
        .where(UploadBatch.started_at < cutoff)
        .values(
            status="failed",
            error_detail={"reason": "worker timeout / crash"},
            completed_at=datetime.now(timezone.utc),
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    count = result.rowcount or 0
    if count:
        logger.warning("Marked %d stale upload batches as failed.", count)
    return count
