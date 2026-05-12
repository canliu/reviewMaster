"""Auth flow tests for Stage 1.

Each test creates a unique email so re-running the suite against the same
database doesn't collide. The `users` and `user_settings` rows accumulate
across runs — acceptable for MVP; wipe with `docker compose down -v` if
hygiene matters.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.main import app
from app.models.user import User
from app.models.user_settings import UserSettings


def _email() -> str:
    # example.com is the RFC 2606 reserved test domain. email-validator
    # rejects .local etc. as special-use names.
    return f"test-{uuid.uuid4().hex[:10]}@example.com"


# Test fixture password — meets policy (letter + digit + 8 chars). Allowlisted
# so detect-secrets stops flagging every `"password":` line in this file.
TEST_PW = "letter1-letter2"  # pragma: allowlist secret


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """One async client per test, with the SQLAlchemy engine's connection
    pool disposed after each test so asyncpg connections don't outlive the
    event loop they were created on (pytest-asyncio gives each test a fresh
    loop)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


# ---------- register ----------

async def test_register_creates_user_and_settings(client: AsyncClient) -> None:
    email = _email()
    response = await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body

    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        assert user is not None
        settings_row = (
            await session.execute(
                select(UserSettings).where(UserSettings.user_id == user.id)
            )
        ).scalar_one_or_none()
        assert settings_row is not None


async def test_register_duplicate_returns_409(client: AsyncClient) -> None:
    email = _email()
    first = await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    assert second.status_code == 409
    assert second.json()["code"] == "EMAIL_EXISTS"


async def test_register_weak_password_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": _email(), "password": "abcdefgh"},  # no digit
    )
    assert response.status_code == 422


# ---------- login ----------

async def test_login_returns_tokens(client: AsyncClient) -> None:
    email = _email()
    await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": TEST_PW}
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body


async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    email = _email()
    await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": "wrong-pw-9"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


# ---------- /me ----------

async def test_me_with_valid_token(client: AsyncClient) -> None:
    email = _email()
    reg = await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    token = reg.json()["access_token"]
    response = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == email


async def test_me_with_expired_token_returns_401(client: AsyncClient) -> None:
    expired_payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
        "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
    }
    expired = jwt.encode(
        expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    response = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {expired}"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_EXPIRED"


# ---------- refresh ----------

async def test_refresh_with_refresh_token_returns_new_access(
    client: AsyncClient,
) -> None:
    email = _email()
    reg = await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    refresh_token = reg.json()["refresh_token"]
    response = await client.post(
        "/api/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == email


async def test_refresh_with_access_token_returns_401(client: AsyncClient) -> None:
    email = _email()
    reg = await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    access_token = reg.json()["access_token"]
    response = await client.post(
        "/api/auth/refresh", json={"refresh_token": access_token}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "WRONG_TOKEN_TYPE"
