"""Synchronous SQLAlchemy engine used by RQ workers.

Workers run inside RQ's synchronous loop. Mixing it with the API's async
engine creates `asyncio.run()` and pool-lifecycle headaches; using a parallel
sync engine keeps the two worlds clean.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _sync_url() -> str:
    # The API's DATABASE_URL uses +asyncpg; swap for sync psycopg2.
    return settings.database_url.replace("+asyncpg", "+psycopg2")


sync_engine = create_engine(_sync_url(), pool_pre_ping=True, future=True)
SyncSessionLocal = sessionmaker(
    bind=sync_engine, expire_on_commit=False, class_=Session
)
