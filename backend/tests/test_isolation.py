"""Cross-user data-isolation tests.

These lock in the contract that one authenticated user can NEVER see another
user's rows, even by guessing UUIDs / shop_site / buyer_key. Every endpoint
that returns user-scoped data has at least one assertion here.
"""
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
from app.models.upload_batch import UploadBatch
from app.models.user import User

TEST_PW = "letter1-letter2"  # pragma: allowlist secret
US_MARKETPLACE = "ATVPDKIKX0DER"


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def _register(client: AsyncClient) -> tuple[User, str]:
    email = f"iso-{uuid.uuid4().hex[:10]}@example.com"
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    token = resp.json()["access_token"]
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one()
    return user, token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_order_for(
    user_id: uuid.UUID, *, order_id: str, shop: str = "p3:US"
) -> Order:
    async with SessionLocal() as session:
        order = Order(
            id=uuid.uuid4(),
            user_id=user_id,
            order_id=order_id,
            shop_site=shop,
            asin="A1",
            order_type="Standard",
            product_name="Widget",
            buyer_email="alice@example.com",
            buyer_key="email:alice@example.com",
            order_time_utc=datetime.now(timezone.utc) - timedelta(days=15),
            estimated_delivery_utc=datetime.now(timezone.utc) - timedelta(days=10),
            item_price=9.99,
            quantity=1,
            currency="USD",
            raw_json={},
        )
        session.add(order)
        # Idempotent stat seed — second order for the same buyer-product would
        # otherwise violate the composite PK.
        existing_stat = await session.get(
            BuyerProductStat,
            {
                "user_id": user_id,
                "shop_site": shop,
                "buyer_key": "email:alice@example.com",
                "grain": "asin",
                "group_value": "A1",
            },
        )
        if existing_stat is None:
            session.add(
                BuyerProductStat(
                    user_id=user_id,
                    shop_site=shop,
                    buyer_key="email:alice@example.com",
                    grain="asin",
                    group_value="A1",
                    order_count=2,
                )
            )
        await session.commit()
        await session.refresh(order)
    return order


async def _seed_batch_for(user_id: uuid.UUID) -> UploadBatch:
    async with SessionLocal() as session:
        b = UploadBatch(
            id=uuid.uuid4(),
            user_id=user_id,
            filename="other-users-file.xlsx",
            file_size_bytes=1234,
            status="completed",
        )
        session.add(b)
        await session.commit()
        await session.refresh(b)
    return b


# ---------- uploads ----------

async def test_uploads_list_is_user_scoped(client: AsyncClient) -> None:
    a, token_a = await _register(client)
    b, _tok_b = await _register(client)
    batch_b = await _seed_batch_for(b.id)

    resp = await client.get("/api/uploads", headers=_auth(token_a))
    body = resp.json()
    assert all(it["id"] != str(batch_b.id) for it in body["items"])
    # And the direct-fetch path: guessing the other user's batch_id → 404.
    direct = await client.get(
        f"/api/uploads/{batch_b.id}", headers=_auth(token_a)
    )
    assert direct.status_code == 404


# ---------- repeat-orders CSV export ----------

async def test_repeat_orders_csv_is_user_scoped(client: AsyncClient) -> None:
    a, token_a = await _register(client)
    b, _tok_b = await _register(client)
    # A has no orders. B has two repeat orders.
    await _seed_order_for(b.id, order_id="B-O1")
    await _seed_order_for(b.id, order_id="B-O2")
    # Set b's active shop (the CSV scopes by active_shop_site OR override).
    async with SessionLocal() as session:
        from app.models.user_settings import UserSettings
        for u in (a, b):
            row = await session.get(UserSettings, u.id)
            row.active_shop_site = "p3:US"
        await session.commit()

    # User A's CSV — no rows.
    csv_resp = await client.get(
        "/api/repeat-orders/export.csv", headers=_auth(token_a)
    )
    rows = list(csv.reader(io.StringIO(csv_resp.text)))
    # Header only.
    assert len(rows) == 1


async def test_review_requests_csv_is_user_scoped(client: AsyncClient) -> None:
    a, token_a = await _register(client)
    b, token_b = await _register(client)
    # B creates a review request.
    order_b = await _seed_order_for(b.id, order_id="B-RR")
    async with SessionLocal() as session:
        from app.models.user_settings import UserSettings
        for u in (a, b):
            row = await session.get(UserSettings, u.id)
            row.active_shop_site = "p3:US"
        await session.commit()
    await client.post(
        "/api/review-requests",
        headers=_auth(token_b),
        json={"order_uuids": [str(order_b.id)], "method": "manual"},
    )

    # A exports — header only.
    csv_resp = await client.get(
        "/api/review-requests/export.csv", headers=_auth(token_a)
    )
    rows = list(csv.reader(io.StringIO(csv_resp.text)))
    assert len(rows) == 1


# ---------- sp-api credentials ----------

async def test_sp_api_credentials_list_is_user_scoped(client: AsyncClient) -> None:
    a, token_a = await _register(client)
    _b, token_b = await _register(client)
    creds = {
        "shop_site": "p3:US",
        "lwa_client_id": "amzn1.application-oa2-client.fake",
        "lwa_client_secret": "fake-secret",  # pragma: allowlist secret
        "refresh_token": "Atzr|FAKE",
        "selling_partner_id": "A1FAKE",
        "marketplace_id": US_MARKETPLACE,
    }
    await client.post("/api/sp-api/credentials", headers=_auth(token_b), json=creds)
    a_list = await client.get("/api/sp-api/credentials", headers=_auth(token_a))
    assert a_list.json() == {"items": []}


# ---------- orders/notes ----------

async def test_order_notes_404_for_other_users_order(client: AsyncClient) -> None:
    a, token_a = await _register(client)
    b, _tok_b = await _register(client)
    order_b = await _seed_order_for(b.id, order_id="OB-NOTE")

    # A tries to add a note on B's order.
    post = await client.post(
        f"/api/orders/{order_b.id}/notes",
        headers=_auth(token_a),
        json={"note": "trying to be naughty"},
    )
    assert post.status_code == 404

    # A tries to list notes on B's order.
    get = await client.get(
        f"/api/orders/{order_b.id}/notes", headers=_auth(token_a)
    )
    assert get.status_code == 404


# ---------- buyer-orders CSV ----------

async def test_buyer_orders_csv_does_not_leak_other_users(
    client: AsyncClient,
) -> None:
    a, token_a = await _register(client)
    b, _tok_b = await _register(client)
    # B's buyer.
    await _seed_order_for(b.id, order_id="B-BO")
    async with SessionLocal() as session:
        from app.models.user_settings import UserSettings
        for u in (a, b):
            row = await session.get(UserSettings, u.id)
            row.active_shop_site = "p3:US"
        await session.commit()

    resp = await client.get(
        "/api/buyers/email:alice@example.com/orders.csv",
        headers=_auth(token_a),
    )
    rows = list(csv.reader(io.StringIO(resp.text)))
    # Header only — A has no orders for this buyer_key in their data.
    assert len(rows) == 1
