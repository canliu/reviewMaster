"""Redis Queue helper. Both API and worker import `get_queue()`."""
from __future__ import annotations

from functools import lru_cache

from redis import Redis
from rq import Queue

from app.core.config import settings


@lru_cache(maxsize=1)
def _redis_connection() -> Redis:
    return Redis.from_url(settings.redis_url)


@lru_cache(maxsize=1)
def get_queue() -> Queue:
    return Queue("default", connection=_redis_connection())
