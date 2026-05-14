"""Cross-shop repeat detection — buyer Alice buys ASIN A1 in p3:US and
again in p4:US (same marketplace, two seller accounts). Under the virtual
`all:US` scope she must show up as a repeat. Different marketplaces stay
separate."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.main import app
from app.models.buyer_product_stat import BuyerProductStat
from app.models.order import Order
from app.models.user import User
from app.models.user_settings import UserSettings

TEST_PW = "letter1-letter2"  # pragma: allowlist secret


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def _register(client: AsyncClient) -> tuple[User, str]:
    email = f"xs-{uuid.uuid4().hex[:10]}@example.com"
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    token = resp.json()["access_token"]
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one()
    return user, token


async def _set_scope(user_id: uuid.UUID, scope: str) -> None:
    async with SessionLocal() as session:
        row = await session.get(UserSettings, user_id)
        row.active_shop_site = scope
        await session.commit()


async def _seed_one_order_one_stat(
    user_id: uuid.UUID, *, shop: str, order_id: str, buyer_email: str = "alice@example.com"
) -> Order:
    """Add a single (count=1) order + stats row in one shop."""
    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)
        order = Order(
            id=uuid.uuid4(),
            user_id=user_id,
            order_id=order_id,
            shop_site=shop,
            asin="A1",
            order_type="Standard",
            buyer_email=buyer_email,
            buyer_key=f"email:{buyer_email}",
            order_time_utc=now - timedelta(days=15),
            estimated_delivery_utc=now - timedelta(days=10),
            item_price=9.99,
            quantity=1,
            raw_json={},
        )
        session.add(order)
        # Only count=1 here — repeat-ness will come from SUM across shops.
        existing = await session.get(
            BuyerProductStat,
            {
                "user_id": user_id,
                "shop_site": shop,
                "buyer_key": f"email:{buyer_email}",
                "grain": "asin",
                "group_value": "A1",
            },
        )
        if existing is None:
            session.add(
                BuyerProductStat(
                    user_id=user_id,
                    shop_site=shop,
                    buyer_key=f"email:{buyer_email}",
                    grain="asin",
                    group_value="A1",
                    order_count=1,
                )
            )
        await session.commit()
        await session.refresh(order)
    return order


async def test_per_shop_scope_does_not_detect_cross_shop_repeat(
    client: AsyncClient,
) -> None:
    user, token = await _register(client)
    # One order each in two same-marketplace shops, each count=1.
    await _seed_one_order_one_stat(user.id, shop="p3:US", order_id="P3-1")
    await _seed_one_order_one_stat(user.id, shop="p4:US", order_id="P4-1")

    await _set_scope(user.id, "p3:US")
    resp = await client.get(
        "/api/repeat-orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["total"] == 0  # only 1 P3 order, not a repeat


async def test_all_market_scope_detects_cross_shop_repeat(
    client: AsyncClient,
) -> None:
    user, token = await _register(client)
    await _seed_one_order_one_stat(user.id, shop="p3:US", order_id="P3-1")
    await _seed_one_order_one_stat(user.id, shop="p4:US", order_id="P4-1")

    await _set_scope(user.id, "all:US")
    resp = await client.get(
        "/api/repeat-orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    assert body["total"] == 2
    by_order = {it["order_id"]: it for it in body["items"]}
    # Both orders carry total_purchases=2 (1 in each shop, summed).
    assert by_order["P3-1"]["total_purchases"] == 2
    assert by_order["P4-1"]["total_purchases"] == 2
    # purchase_index orders by time across the pooled shops.
    assert {by_order["P3-1"]["purchase_index"], by_order["P4-1"]["purchase_index"]} == {1, 2}


async def test_cross_marketplace_stays_separate(client: AsyncClient) -> None:
    user, token = await _register(client)
    # Same buyer email shows up in US and CA — but Amazon's anonymized
    # emails are per-marketplace anyway, so this is the worst case we'd see.
    # Our virtual `all:US` scope must not merge across marketplaces.
    await _seed_one_order_one_stat(user.id, shop="p3:US", order_id="US-1")
    await _seed_one_order_one_stat(user.id, shop="p3:CA", order_id="CA-1")
    await _set_scope(user.id, "all:US")
    resp = await client.get(
        "/api/repeat-orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["total"] == 0  # CA order isn't pooled into US scope


async def test_available_scopes_lists_marketplace_when_multi_shop(
    client: AsyncClient,
) -> None:
    user, token = await _register(client)
    await _seed_one_order_one_stat(user.id, shop="p3:US", order_id="A")
    await _seed_one_order_one_stat(user.id, shop="p4:US", order_id="B")
    await _seed_one_order_one_stat(user.id, shop="p3:CA", order_id="C")
    resp = await client.get(
        "/api/settings",
        headers={"Authorization": f"Bearer {token}"},
    )
    scopes = resp.json()["available_scopes"]
    values = [s["value"] for s in scopes]
    # US has 2 shops → an `all:US` entry exists; CA has 1 shop → no `all:CA`.
    assert "all:US" in values
    assert "all:CA" not in values
    assert "p3:US" in values and "p4:US" in values and "p3:CA" in values
