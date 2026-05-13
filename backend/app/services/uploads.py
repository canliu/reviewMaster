"""Upload API service: save the file, create the batch, enqueue the job."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.queue import get_queue
from app.models.upload_batch import UploadBatch

UPLOADS_DIR = Path("/tmp/uploads")
MAX_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".xlsx"}


async def receive_upload(
    db: AsyncSession, user_id: UUID, upload: UploadFile
) -> UploadBatch:
    filename = upload.filename or "upload.xlsx"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise APIError(400, "UNSUPPORTED_FILE_TYPE", "Only .xlsx files are accepted.")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    batch_id = uuid.uuid4()
    file_path = UPLOADS_DIR / f"{batch_id}.xlsx"

    # Stream to disk and track size; fail closed if it exceeds the limit.
    size = 0
    with open(file_path, "wb") as fh:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                fh.close()
                file_path.unlink(missing_ok=True)
                raise APIError(
                    413,
                    "FILE_TOO_LARGE",
                    f"File exceeds the {MAX_BYTES // (1024 * 1024)} MB limit.",
                )
            fh.write(chunk)

    batch = UploadBatch(
        id=batch_id,
        user_id=user_id,
        filename=filename,
        file_size_bytes=size,
        status="processing",
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    # Enqueue by import path so the worker doesn't need anything more than
    # the shared codebase.
    get_queue().enqueue(
        "app.workers.upload.process_upload",
        str(batch_id),
        str(user_id),
        str(file_path),
        job_timeout=60 * 30,  # 30 minutes for very large files
    )

    return batch
