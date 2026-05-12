from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID

import bcrypt
import jwt

from app.core.config import settings

# bcrypt 4.x dropped its `__about__` attribute, so passlib's bcrypt backend
# breaks. Calling bcrypt directly avoids the indirection entirely.

TokenType = Literal["access", "refresh"]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _create_token(sub: UUID, token_type: TokenType, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(sub),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID) -> str:
    return _create_token(
        user_id, "access", timedelta(minutes=settings.access_token_ttl_minutes)
    )


def create_refresh_token(user_id: UUID) -> str:
    return _create_token(
        user_id, "refresh", timedelta(days=settings.refresh_token_ttl_days)
    )


def decode_token(token: str) -> dict[str, Any]:
    """Return the JWT payload or raise jwt.PyJWTError on any failure
    (signature, expiry, malformed)."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
