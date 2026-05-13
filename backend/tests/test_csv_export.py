"""CSV export tests for Stage 5."""
from __future__ import annotations

import csv
import io
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


async def _setup_user_with_two_repeat_orders() -> tuple[str, list[Order]]:
    """Returns (token, [order1, order2])."""
    email = f"csv-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as session:
        pass  # placeholder
    # Register via API to get a token + matching user_settings.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await c.post(
            "/api/auth/register",
            json={"email": email, "password": TEST_PW},
        )
        token = reg.json()["access_token"]

    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one()
        settings = await session.get(UserSettings, user.id)
        settings.active_shop_site = "p3:US"
        await session.commit()

        now = datetime.now(timezone.utc)
        orders = []
        for idx in (1, 2):
            o = Order(
                id=uuid.uuid4(),
                user_id=user.id,
                order_id=f"CSV-{idx}",
                shop_site="p3:US",
                asin="A1",
                order_type="Standard",
                product_name="Widget",
                buyer_email="alice@example.com",
                buyer_key="email:alice@example.com",
                order_time_utc=now - timedelta(days=15 + idx),
                estimated_delivery_utc=now - timedelta(days=10),
                item_price=9.99,
                quantity=1,
                ship_city="Austin",
                ship_state="TX",
                ship_country="US",
                currency="USD",
                raw_json={},
            )
            session.add(o)
            orders.append(o)
        session.add(
            BuyerProductStat(
                user_id=user.id,
                shop_site="p3:US",
                buyer_key="email:alice@example.com",
                grain="asin",
                group_value="A1",
                order_count=2,
            )
        )
        await session.commit()
        for o in orders:
            await session.refresh(o)
    return token, orders


async def test_repeat_orders_csv_header_and_row_count(client: AsyncClient) -> None:
    token, orders = await _setup_user_with_two_repeat_orders()
    headers = {"Authorization": f"Bearer {token}"}

    csv_resp = await client.get("/api/repeat-orders/export.csv", headers=headers)
    assert csv_resp.status_code == 200
    cd = csv_resp.headers.get("content-disposition", "")
    assert "attachment" in cd.lower()

    text = csv_resp.text
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    assert len(rows) == 1 + len(orders)  # header + N
    header = rows[0]
    assert header[0] == "order_id"
    assert "purchase_index" in header
    assert "can_request_review" in header

    list_resp = await client.get("/api/repeat-orders", headers=headers)
    assert list_resp.json()["total"] == len(orders)


async def test_review_requests_csv_header_and_attachment(
    client: AsyncClient,
) -> None:
    token, orders = await _setup_user_with_two_repeat_orders()
    headers = {"Authorization": f"Bearer {token}"}

    # Create one manual request so the CSV has at least one data row.
    await client.post(
        "/api/review-requests",
        headers=headers,
        json={"order_uuids": [str(orders[0].id)], "method": "manual"},
    )

    csv_resp = await client.get(
        "/api/review-requests/export.csv", headers=headers
    )
    assert csv_resp.status_code == 200
    assert "attachment" in csv_resp.headers.get("content-disposition", "").lower()

    reader = csv.reader(io.StringIO(csv_resp.text))
    rows = list(reader)
    assert rows[0][0] == "order_id"
    assert "request_method" in rows[0]
    assert "notes_count" in rows[0]
    assert len(rows) == 2  # header + 1 created request
