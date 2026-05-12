from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.models.user_settings import UserSettings


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def register_user(db: AsyncSession, email: str, password: str) -> User:
    """Create a user + matching user_settings row in a single transaction.

    Raises APIError(409, EMAIL_EXISTS) on duplicate email.
    """
    normalized = _normalize_email(email)
    user = User(email=normalized, password_hash=hash_password(password))
    db.add(user)
    try:
        await db.flush()  # populate user.id, surface IntegrityError early
    except IntegrityError as exc:
        await db.rollback()
        raise APIError(409, "EMAIL_EXISTS", "Email is already registered.") from exc

    db.add(UserSettings(user_id=user.id))
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    """Return the user or raise APIError(401, INVALID_CREDENTIALS).

    The same error is raised whether the email doesn't exist or the password
    is wrong — never leak which one.
    """
    normalized = _normalize_email(email)
    result = await db.execute(select(User).where(User.email == normalized))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise APIError(401, "INVALID_CREDENTIALS", "Invalid email or password.")
    return user


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
