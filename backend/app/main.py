from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.orders import router as orders_router
from app.api.repeat_orders import router as repeat_orders_router
from app.api.review_requests import router as review_requests_router
from app.api.settings import router as settings_router
from app.api.sp_api import router as sp_api_router
from app.api.uploads import router as uploads_router
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.errors import register_exception_handlers
from app.core.logger import get_logger
from app.services.sweeper import sweep_stale_batches

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # On startup: clean up any upload batches stuck in `processing` from a
    # previous worker crash. Failure here logs but does not block boot.
    try:
        async with SessionLocal() as db:
            await sweep_stale_batches(db)
    except Exception:  # noqa: BLE001
        logger.exception("startup sweeper failed")
    yield


app = FastAPI(
    title="ReviewMaster API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth_router)
app.include_router(uploads_router)
app.include_router(settings_router)
app.include_router(repeat_orders_router)
app.include_router(review_requests_router)
app.include_router(orders_router)
app.include_router(sp_api_router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
