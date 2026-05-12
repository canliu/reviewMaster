from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import APIError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.schemas.auth import (
    AccessTokenOnly,
    LoginIn,
    MeOut,
    RefreshIn,
    RegisterIn,
    TokenPair,
)
from app.services.auth import authenticate, get_user_by_id, register_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterIn, db: AsyncSession = Depends(get_db)
) -> TokenPair:
    user = await register_user(db, body.email, body.password)
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenPair)
async def login(body: LoginIn, db: AsyncSession = Depends(get_db)) -> TokenPair:
    user = await authenticate(db, body.email, body.password)
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=AccessTokenOnly)
async def refresh(
    body: RefreshIn, db: AsyncSession = Depends(get_db)
) -> AccessTokenOnly:
    try:
        payload = decode_token(body.refresh_token)
    except jwt.ExpiredSignatureError as exc:
        raise APIError(401, "TOKEN_EXPIRED", "Refresh token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise APIError(401, "INVALID_TOKEN", "Refresh token is invalid.") from exc

    if payload.get("type") != "refresh":
        raise APIError(401, "WRONG_TOKEN_TYPE", "Refresh token required.")

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise APIError(401, "INVALID_TOKEN", "Refresh token is invalid.") from exc

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise APIError(401, "USER_NOT_FOUND", "User no longer exists.")

    return AccessTokenOnly(access_token=create_access_token(user.id))


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut(id=user.id, email=user.email, timezone=user.timezone)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(_user: User = Depends(get_current_user)) -> Response:
    # Stateless JWT — the client discards its tokens. We keep this endpoint
    # so the API surface is symmetric and so future stages can hook session
    # invalidation here if we move to a revocation list.
    return Response(status_code=status.HTTP_204_NO_CONTENT)
