"""Review-requests endpoint tests for Stage 5."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.main import app
from app.models.buyer_product_stat import BuyerProductStat
from app.models.order import Order
from app.models.review_request import ReviewRequest
from app.models.review_request_note import ReviewRequestNote
from app.models.user import User
from app.models.user_settings import UserSettings
from app.services.seller_central import build_seller_central_url

TEST_PW = "letter1-letter2"  # pragma: allowlist secret


def _email() -> str:
    return f"test-{uuid.uuid4().hex[:10]}@example.com"


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


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


async def _set_active_shop(user_id, shop: str = "p3:US") -> None:
    async with SessionLocal() as session:
        row = await session.get(UserSettings, user_id)
        assert row is not None
        row.active_shop_site = shop
        await session.commit()


async def _seed_repeat_order(
    user_id,
    *,
    order_id: str = "O1",
    shop: str = "p3:US",
    asin: str = "A1",
    buyer_email: str = "alice@example.com",
    estimated_delivery_days_ago: float = 10,
    seed_stats: bool = True,
) -> Order:
    """Drop an order + (optionally) the matching repeat-stats row."""
    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)
        order = Order(
            id=uuid.uuid4(),
            user_id=user_id,
            order_id=order_id,
            shop_site=shop,
            asin=asin,
            order_type="Standard",
            buyer_email=buyer_email,
            buyer_key=f"email:{buyer_email}",
            order_time_utc=now - timedelta(days=15),
            estimated_delivery_utc=now - timedelta(days=estimated_delivery_days_ago),
            item_price=9.99,
            quantity=1,
            raw_json={},
        )
        session.add(order)
        if seed_stats:
            session.add(
                BuyerProductStat(
                    user_id=user_id,
                    shop_site=shop,
                    buyer_key=f"email:{buyer_email}",
                    grain="asin",
                    group_value=asin,
                    order_count=2,
                )
            )
        await session.commit()
        await session.refresh(order)
    return order


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------- create ----------

async def test_non_repeat_order_rejected(client: AsyncClient) -> None:
    user, token = await _register(client)
    await _set_active_shop(user.id)
    order = await _seed_repeat_order(user.id, seed_stats=False)
    resp = await client.post(
        "/api/review-requests",
        headers=_auth(token),
        json={"order_uuids": [str(order.id)], "method": "manual"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["created"] == []
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == "NOT_A_REPEAT_ORDER"


async def test_out_of_window_rejected(client: AsyncClient) -> None:
    user, token = await _register(client)
    await _set_active_shop(user.id)
    order = await _seed_repeat_order(
        user.id, estimated_delivery_days_ago=2  # too early
    )
    resp = await client.post(
        "/api/review-requests",
        headers=_auth(token),
        json={"order_uuids": [str(order.id)], "method": "manual"},
    )
    body = resp.json()
    assert body["errors"][0]["code"] == "OUT_OF_WINDOW"


async def test_already_sent_is_skipped(client: AsyncClient) -> None:
    user, token = await _register(client)
    await _set_active_shop(user.id)
    order = await _seed_repeat_order(user.id)
    # Pre-existing sent request
    async with SessionLocal() as s:
        s.add(
            ReviewRequest(
                id=uuid.uuid4(), user_id=user.id, order_uuid=order.id,
                method="manual", status="sent",
            )
        )
        await s.commit()
    resp = await client.post(
        "/api/review-requests",
        headers=_auth(token),
        json={"order_uuids": [str(order.id)], "method": "manual"},
    )
    body = resp.json()
    assert body["created"] == []
    assert body["errors"] == []
    assert body["skipped"][0]["reason"] == "already requested"


async def test_bulk_with_mixed_valid_invalid(client: AsyncClient) -> None:
    user, token = await _register(client)
    await _set_active_shop(user.id)
    good = await _seed_repeat_order(user.id, order_id="OK")
    bad = await _seed_repeat_order(
        user.id, order_id="BAD", asin="A2", estimated_delivery_days_ago=2,
    )
    resp = await client.post(
        "/api/review-requests",
        headers=_auth(token),
        json={
            "order_uuids": [str(good.id), str(bad.id)],
            "method": "manual",
        },
    )
    body = resp.json()
    assert len(body["created"]) == 1
    assert body["created"][0]["order_uuid"] == str(good.id)
    assert len(body["errors"]) == 1
    assert body["errors"][0]["order_uuid"] == str(bad.id)


# ---------- redirect URL ----------

def test_build_seller_central_url_known_markets() -> None:
    cases = {
        "p3:US": "https://sellercentral.amazon.com/orders-v3/order/X1",
        "p3:UK": "https://sellercentral.amazon.co.uk/orders-v3/order/X1",
        "p3:DE": "https://sellercentral.amazon.de/orders-v3/order/X1",
        "p3:JP": "https://sellercentral.amazon.co.jp/orders-v3/order/X1",
    }
    for shop, expected in cases.items():
        assert build_seller_central_url(shop, "X1") == expected


def test_build_seller_central_url_unknown_raises() -> None:
    from app.core.errors import APIError

    with pytest.raises(APIError) as exc:
        build_seller_central_url("p3:ZZ", "X1")
    assert exc.value.code == "UNSUPPORTED_MARKETPLACE"


# ---------- confirm pending ----------

async def test_pending_link_confirms_to_sent(client: AsyncClient) -> None:
    user, token = await _register(client)
    await _set_active_shop(user.id)
    order = await _seed_repeat_order(user.id)
    resp = await client.post(
        "/api/review-requests",
        headers=_auth(token),
        json={"order_uuids": [str(order.id)], "method": "link"},
    )
    body = resp.json()
    created_id = body["created"][0]["id"]
    assert body["created"][0]["redirect_url"]
    assert body["created"][0]["status"] == "pending"

    confirm = await client.patch(
        f"/api/review-requests/{created_id}/confirm", headers=_auth(token)
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "sent"


async def test_confirm_already_sent_returns_422(client: AsyncClient) -> None:
    user, token = await _register(client)
    await _set_active_shop(user.id)
    order = await _seed_repeat_order(user.id)
    create_resp = await client.post(
        "/api/review-requests",
        headers=_auth(token),
        json={"order_uuids": [str(order.id)], "method": "manual"},
    )
    created_id = create_resp.json()["created"][0]["id"]
    confirm = await client.patch(
        f"/api/review-requests/{created_id}/confirm", headers=_auth(token)
    )
    assert confirm.status_code == 422
    assert confirm.json()["code"] == "NOT_PENDING"


# ---------- failed retry ----------

async def test_failed_retry_preserves_notes_and_supersession(
    client: AsyncClient,
) -> None:
    user, token = await _register(client)
    await _set_active_shop(user.id)
    order = await _seed_repeat_order(user.id)

    # Seed a failed review_request with two user notes attached.
    async with SessionLocal() as s:
        failed = ReviewRequest(
            id=uuid.uuid4(), user_id=user.id, order_uuid=order.id,
            method="api", status="failed",
        )
        s.add(failed)
        await s.flush()
        s.add(ReviewRequestNote(
            user_id=user.id, order_uuid=order.id, review_request_id=failed.id,
            note="first context note", kind="user",
        ))
        s.add(ReviewRequestNote(
            user_id=user.id, order_uuid=order.id, review_request_id=failed.id,
            note="second context note", kind="user",
        ))
        await s.commit()
        old_id = failed.id

    # Manual retry.
    resp = await client.post(
        "/api/review-requests",
        headers=_auth(token),
        json={"order_uuids": [str(order.id)], "method": "manual"},
    )
    body = resp.json()
    assert len(body["created"]) == 1
    new_id = body["created"][0]["id"]
    assert body["created"][0]["status"] == "sent"
    assert new_id != str(old_id)

    # Old request is gone; the two user notes still exist; one new system note.
    async with SessionLocal() as s:
        old = (
            await s.execute(select(ReviewRequest).where(ReviewRequest.id == old_id))
        ).scalar_one_or_none()
        assert old is None

        notes = (
            await s.execute(
                select(ReviewRequestNote)
                .where(ReviewRequestNote.order_uuid == order.id)
                .order_by(ReviewRequestNote.created_at)
            )
        ).scalars().all()
        kinds = [n.kind for n in notes]
        # 2 original user notes + 1 system supersession note.
        assert kinds.count("user") == 2
        assert kinds.count("system") == 1


# ---------- notes append-only ----------

async def test_notes_have_no_patch_or_delete(client: AsyncClient) -> None:
    user, token = await _register(client)
    await _set_active_shop(user.id)
    order = await _seed_repeat_order(user.id)
    await client.post(
        f"/api/orders/{order.id}/notes",
        headers=_auth(token),
        json={"note": "hello"},
    )
    # No such routes exist.
    p = await client.patch(
        f"/api/orders/{order.id}/notes", headers=_auth(token), json={"note": "x"}
    )
    assert p.status_code in (404, 405)
    d = await client.delete(f"/api/orders/{order.id}/notes", headers=_auth(token))
    assert d.status_code in (404, 405)


# ---------- cross-user isolation ----------

async def test_cross_user_cannot_request_on_others_order(
    client: AsyncClient,
) -> None:
    user_a, token_a = await _register(client)
    user_b, _token_b = await _register(client)
    await _set_active_shop(user_b.id)
    order_b = await _seed_repeat_order(user_b.id)

    # User A guesses B's order_uuid.
    await _set_active_shop(user_a.id)
    resp = await client.post(
        "/api/review-requests",
        headers=_auth(token_a),
        json={"order_uuids": [str(order_b.id)], "method": "manual"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"
