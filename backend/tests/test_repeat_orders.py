"""Repeat-orders endpoint tests for Stage 4.

These bypass the upload worker and seed `orders` + `buyer_product_stats`
directly so we can craft small, deterministic fixtures (one buyer with one
purchase shouldn't appear, one with two should, etc).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterable

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.main import app
from app.models.buyer_product_stat import BuyerProductStat
from app.models.order import Order
from app.models.review_request import ReviewRequest
from app.models.user import User
from app.models.user_settings import UserSettings

TEST_PW = "letter1-letter2"  # pragma: allowlist secret


def _email() -> str:
    return f"test-{uuid.uuid4().hex[:10]}@example.com"


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


# ---------- seed helpers ----------

async def _register(client: AsyncClient) -> tuple[User, str]:
    email = _email()
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one()
    return user, token


async def _set_settings(
    user_id: uuid.UUID,
    *,
    active_shop: str = "p3:US",
    grain: str = "asin",
    excluded: list[str] | None = None,
) -> None:
    async with SessionLocal() as session:
        row = await session.get(UserSettings, user_id)
        assert row is not None
        row.active_shop_site = active_shop
        row.repeat_grain = grain
        row.excluded_order_types = excluded or []
        await session.commit()


async def _add_order(
    user_id: uuid.UUID,
    *,
    order_id: str,
    shop_site: str = "p3:US",
    asin: str | None = "A1",
    spu: str | None = None,
    product_name: str | None = None,
    buyer_email: str | None = "alice@example.com",
    order_time_utc: datetime | None = None,
    estimated_delivery_utc: datetime | None = None,
    order_type: str | None = "Standard",
    item_price: float = 9.99,
    quantity: int = 1,
) -> Order:
    async with SessionLocal() as session:
        order = Order(
            id=uuid.uuid4(),
            user_id=user_id,
            order_id=order_id,
            shop_site=shop_site,
            asin=asin,
            spu=spu,
            product_name=product_name,
            order_type=order_type,
            buyer_email=buyer_email,
            buyer_key=f"email:{buyer_email}" if buyer_email else f"addr:{shop_site}",
            order_time_utc=order_time_utc or datetime.now(timezone.utc) - timedelta(days=10),
            estimated_delivery_utc=estimated_delivery_utc,
            item_price=item_price,
            quantity=quantity,
            raw_json={},
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
    return order


async def _add_stat(
    user_id: uuid.UUID,
    *,
    shop_site: str,
    buyer_key: str,
    grain: str,
    group_value: str,
    order_count: int,
) -> None:
    async with SessionLocal() as session:
        # Upsert: stats may already exist from a previous _add_stat call.
        existing = await session.get(
            BuyerProductStat,
            {
                "user_id": user_id,
                "shop_site": shop_site,
                "buyer_key": buyer_key,
                "grain": grain,
                "group_value": group_value,
            },
        )
        if existing is None:
            session.add(
                BuyerProductStat(
                    user_id=user_id,
                    shop_site=shop_site,
                    buyer_key=buyer_key,
                    grain=grain,
                    group_value=group_value,
                    order_count=order_count,
                )
            )
        else:
            existing.order_count = order_count
        await session.commit()


async def _add_review_request(
    user_id: uuid.UUID, order_uuid: uuid.UUID, *, status: str = "sent",
    method: str = "manual",
) -> None:
    async with SessionLocal() as session:
        session.add(
            ReviewRequest(
                id=uuid.uuid4(),
                user_id=user_id,
                order_uuid=order_uuid,
                status=status,
                method=method,
            )
        )
        await session.commit()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------- tests ----------

async def test_single_purchase_is_excluded(client: AsyncClient) -> None:
    user, token = await _register(client)
    await _set_settings(user.id)
    await _add_order(user.id, order_id="O1")
    # No stats row added — buyer_product_stats says no repeat. List should be empty.
    response = await client.get("/api/repeat-orders", headers=_auth_header(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


async def test_two_purchases_appear_with_indices(client: AsyncClient) -> None:
    user, token = await _register(client)
    await _set_settings(user.id)
    base = datetime.now(timezone.utc) - timedelta(days=20)
    await _add_order(user.id, order_id="O1", order_time_utc=base)
    await _add_order(user.id, order_id="O2", order_time_utc=base + timedelta(days=2))
    await _add_stat(
        user.id,
        shop_site="p3:US",
        buyer_key="email:alice@example.com",
        grain="asin",
        group_value="A1",
        order_count=2,
    )

    response = await client.get("/api/repeat-orders", headers=_auth_header(token))
    body = response.json()
    assert body["total"] == 2
    by_order = {item["order_id"]: item for item in body["items"]}
    assert by_order["O1"]["purchase_index"] == 1
    assert by_order["O1"]["total_purchases"] == 2
    assert by_order["O2"]["purchase_index"] == 2


async def test_grain_change_regroups(client: AsyncClient) -> None:
    """Same buyer, two different ASINs sharing one SPU. ASIN grain → not repeat
    (each ASIN once). SPU grain → repeat (SPU appears twice)."""
    user, token = await _register(client)
    await _set_settings(user.id, grain="asin")
    base = datetime.now(timezone.utc) - timedelta(days=20)
    await _add_order(
        user.id, order_id="O1", asin="A1", spu="S1", order_time_utc=base
    )
    await _add_order(
        user.id, order_id="O2", asin="A2", spu="S1",
        order_time_utc=base + timedelta(days=2),
    )
    # No ASIN-grain repeats: each ASIN once.
    # Add an SPU-grain stat with order_count=2.
    await _add_stat(
        user.id,
        shop_site="p3:US",
        buyer_key="email:alice@example.com",
        grain="spu",
        group_value="S1",
        order_count=2,
    )

    # ASIN grain → empty
    response = await client.get("/api/repeat-orders", headers=_auth_header(token))
    assert response.json()["total"] == 0

    # Flip to SPU → both orders show up
    await _set_settings(user.id, grain="spu")
    response = await client.get("/api/repeat-orders", headers=_auth_header(token))
    assert response.json()["total"] == 2


async def test_excluded_order_type_removes_orders(client: AsyncClient) -> None:
    user, token = await _register(client)
    await _set_settings(user.id, excluded=["Refund"])
    base = datetime.now(timezone.utc) - timedelta(days=20)
    await _add_order(user.id, order_id="O1", order_time_utc=base, order_type="Standard")
    await _add_order(
        user.id, order_id="O2", order_time_utc=base + timedelta(days=2),
        order_type="Refund",
    )
    await _add_stat(
        user.id, shop_site="p3:US", buyer_key="email:alice@example.com",
        grain="asin", group_value="A1", order_count=2,
    )

    response = await client.get("/api/repeat-orders", headers=_auth_header(token))
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["order_id"] == "O1"


async def test_in_window_filter(client: AsyncClient) -> None:
    user, token = await _register(client)
    await _set_settings(user.id)
    now = datetime.now(timezone.utc)
    # Too early (3 days ago), in-window (10 days ago), too late (40 days ago).
    await _add_order(
        user.id, order_id="EARLY",
        order_time_utc=now - timedelta(days=15),
        estimated_delivery_utc=now - timedelta(days=3),
    )
    await _add_order(
        user.id, order_id="IN",
        order_time_utc=now - timedelta(days=15),
        estimated_delivery_utc=now - timedelta(days=10),
    )
    await _add_order(
        user.id, order_id="LATE",
        order_time_utc=now - timedelta(days=15),
        estimated_delivery_utc=now - timedelta(days=40),
    )
    await _add_stat(
        user.id, shop_site="p3:US", buyer_key="email:alice@example.com",
        grain="asin", group_value="A1", order_count=3,
    )

    response = await client.get(
        "/api/repeat-orders?in_window=true", headers=_auth_header(token)
    )
    body = response.json()
    assert {item["order_id"] for item in body["items"]} == {"IN"}


async def test_has_review_request_false_excludes_any_request(
    client: AsyncClient,
) -> None:
    user, token = await _register(client)
    await _set_settings(user.id)
    base = datetime.now(timezone.utc) - timedelta(days=20)
    o1 = await _add_order(user.id, order_id="O1", order_time_utc=base)
    o2 = await _add_order(
        user.id, order_id="O2", order_time_utc=base + timedelta(days=2)
    )
    await _add_stat(
        user.id, shop_site="p3:US", buyer_key="email:alice@example.com",
        grain="asin", group_value="A1", order_count=2,
    )
    # O1 has a failed request (per prompt: still counts as "has a row")
    await _add_review_request(user.id, o1.id, status="failed")

    response = await client.get(
        "/api/repeat-orders?has_review_request=false", headers=_auth_header(token)
    )
    body = response.json()
    assert {item["order_id"] for item in body["items"]} == {"O2"}


async def test_can_request_review_only_blocked_by_active(client: AsyncClient) -> None:
    user, token = await _register(client)
    await _set_settings(user.id)
    now = datetime.now(timezone.utc)
    # Both in window.
    o1 = await _add_order(
        user.id, order_id="O1",
        order_time_utc=now - timedelta(days=15),
        estimated_delivery_utc=now - timedelta(days=10),
    )
    o2 = await _add_order(
        user.id, order_id="O2",
        order_time_utc=now - timedelta(days=15),
        estimated_delivery_utc=now - timedelta(days=10),
    )
    await _add_stat(
        user.id, shop_site="p3:US", buyer_key="email:alice@example.com",
        grain="asin", group_value="A1", order_count=2,
    )
    # O1: an active request blocks; O2: only a failed request → doesn't block.
    await _add_review_request(user.id, o1.id, status="sent")
    await _add_review_request(user.id, o2.id, status="failed")

    response = await client.get("/api/repeat-orders", headers=_auth_header(token))
    by_order = {item["order_id"]: item for item in response.json()["items"]}
    assert by_order["O1"]["can_request_review"] is False
    assert by_order["O1"]["can_request_reason"] == "already requested"
    assert by_order["O2"]["can_request_review"] is True


async def test_cross_user_isolation(client: AsyncClient) -> None:
    user_a, token_a = await _register(client)
    user_b, _token_b = await _register(client)
    await _set_settings(user_a.id)
    await _set_settings(user_b.id)
    base = datetime.now(timezone.utc) - timedelta(days=10)

    # User B has the repeat orders.
    await _add_order(
        user_b.id, order_id="OB1", buyer_email="bob@example.com",
        order_time_utc=base,
    )
    o_b2 = await _add_order(
        user_b.id, order_id="OB2", buyer_email="bob@example.com",
        order_time_utc=base + timedelta(days=2),
    )
    await _add_stat(
        user_b.id, shop_site="p3:US", buyer_key="email:bob@example.com",
        grain="asin", group_value="A1", order_count=2,
    )

    # User A's list must be empty.
    response = await client.get("/api/repeat-orders", headers=_auth_header(token_a))
    assert response.json()["total"] == 0

    # User A guessing User B's order_uuid → 404, never leak content.
    response = await client.get(
        f"/api/repeat-orders/{o_b2.id}", headers=_auth_header(token_a)
    )
    assert response.status_code == 404
