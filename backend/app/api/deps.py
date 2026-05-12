from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import APIError
from app.core.security import decode_token
from app.models.user import User
from app.services.auth import get_user_by_id


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the bearer token to a User. Raises 401 on any failure.

    Every protected route from Stage 1 onward depends on this — it is the
    single seam where the JWT contract is enforced.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise APIError(401, "MISSING_TOKEN", "Authorization header is required.")
    token = authorization.split(" ", 1)[1].strip()

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise APIError(401, "TOKEN_EXPIRED", "Token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise APIError(401, "INVALID_TOKEN", "Token is invalid.") from exc

    if payload.get("type") != "access":
        raise APIError(401, "WRONG_TOKEN_TYPE", "Access token required.")

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise APIError(401, "INVALID_TOKEN", "Token is invalid.") from exc

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise APIError(401, "USER_NOT_FOUND", "User no longer exists.")
    return user
