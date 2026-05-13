"""Settings API tests for Stage 3."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert

from app.core.db import SessionLocal, engine
from app.main import app
from app.models.order import Order

TEST_PW = "letter1-letter2"  # pragma: allowlist secret


def _email() -> str:
    return f"test-{uuid.uuid4().hex[:10]}@example.com"


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def _register(client: AsyncClient) -> tuple[str, str]:
    email = _email()
    response = await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    return email, response.json()["access_token"]


async def _seed_orders(user_email: str, shop_site: str, order_type: str) -> None:
    """Insert one order for the given user/shop/type so the available-* lists
    have something to return."""
    async with SessionLocal() as session:
        from app.models.user import User
        from sqlalchemy import select

        user = (
            await session.execute(select(User).where(User.email == user_email))
        ).scalar_one()
        await session.execute(
            insert(Order).values(
                id=uuid.uuid4(),
                user_id=user.id,
                order_id=f"O-{uuid.uuid4().hex[:8]}",
                shop_site=shop_site,
                order_type=order_type,
                buyer_key=f"email:{user_email}",
                raw_json={},
            )
        )
        await session.commit()


# ---------- defaults ----------

async def test_defaults_for_new_user(client: AsyncClient) -> None:
    _, token = await _register(client)
    response = await client.get(
        "/api/settings", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["active_shop_site"] is None
    assert body["repeat_grain"] == "asin"
    assert body["excluded_order_types"] == []
    assert body["timezone"] == "UTC"
    assert body["available_shop_sites"] == []
    assert body["available_order_types"] == []


# ---------- available_* derives from this user only ----------

async def test_available_shops_scoped_to_user(client: AsyncClient) -> None:
    email_a, token_a = await _register(client)
    email_b, _token_b = await _register(client)

    await _seed_orders(email_a, "p3:US", "Standard")
    await _seed_orders(email_a, "p3:CA", "Standard")
    await _seed_orders(email_b, "p3:UK", "Standard")

    response = await client.get(
        "/api/settings", headers={"Authorization": f"Bearer {token_a}"}
    )
    body = response.json()
    assert set(body["available_shop_sites"]) == {"p3:US", "p3:CA"}
    assert "p3:UK" not in body["available_shop_sites"]


# ---------- patch validation ----------

async def test_patch_rejects_unknown_shop(client: AsyncClient) -> None:
    email, token = await _register(client)
    await _seed_orders(email, "p3:US", "Standard")
    response = await client.patch(
        "/api/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"active_shop_site": "p3:DOESNOTEXIST"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_SHOP_SITE"


async def test_patch_rejects_invalid_timezone(client: AsyncClient) -> None:
    _, token = await _register(client)
    response = await client.patch(
        "/api/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"timezone": "Mars/Olympus_Mons"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_TIMEZONE"


async def test_patch_rejects_invalid_grain(client: AsyncClient) -> None:
    _, token = await _register(client)
    response = await client.patch(
        "/api/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"repeat_grain": "loose-vibes"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REPEAT_GRAIN"


# ---------- happy-path patch ----------

async def test_patch_updates_and_returns_new_state(client: AsyncClient) -> None:
    email, token = await _register(client)
    await _seed_orders(email, "p3:US", "Standard")
    await _seed_orders(email, "p3:US", "Refund")  # gives us a second order_type

    response = await client.patch(
        "/api/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "active_shop_site": "p3:US",
            "repeat_grain": "spu",
            "excluded_order_types": ["Refund"],
            "timezone": "America/New_York",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["active_shop_site"] == "p3:US"
    assert body["repeat_grain"] == "spu"
    assert body["excluded_order_types"] == ["Refund"]
    assert body["timezone"] == "America/New_York"
