"""Worker tests for the SP-API solicitations job. Mocks the SP-API client
seam and the rate-limit acquire so tests are fast and deterministic."""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.main import app
from app.models.order import Order
from app.models.review_request import ReviewRequest
from app.models.seller_credential import SellerCredential
from app.models.user import User
from app.services import sp_api_credentials
from app.workers.solicitations import send_solicitation

TEST_PW = "letter1-letter2"  # pragma: allowlist secret
US_MARKETPLACE = "ATVPDKIKX0DER"


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def _setup_user_order_and_creds(
    client: AsyncClient,
) -> tuple[uuid.UUID, ReviewRequest]:
    """Register, save SP-API creds, seed an in-window order + a pending
    review_request — return (user_id, review_request)."""
    email = f"wk-{uuid.uuid4().hex[:10]}@example.com"
    reg = await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/sp-api/credentials",
        headers=headers,
        json={
            "lwa_client_id": "amzn1.application-oa2-client.fake",
            "lwa_client_secret": "fake-secret",  # pragma: allowlist secret
            "refresh_token": "Atzr|FAKE",
            "selling_partner_id": "A1FAKE",
            "marketplace_id": US_MARKETPLACE,
        },
    )

    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one()
        order = Order(
            id=uuid.uuid4(),
            user_id=user.id,
            order_id=f"112-{uuid.uuid4().hex[:8]}",
            shop_site="p3:US",
            asin="A1",
            order_type="Standard",
            buyer_email="alice@example.com",
            buyer_key="email:alice@example.com",
            order_time_utc=now - timedelta(days=15),
            estimated_delivery_utc=now - timedelta(days=10),
            item_price=9.99,
            quantity=1,
            raw_json={},
        )
        rr = ReviewRequest(
            id=uuid.uuid4(),
            user_id=user.id,
            order_uuid=order.id,
            method="api",
            status="pending",
        )
        session.add(order)
        await session.flush()
        session.add(rr)
        await session.commit()
        await session.refresh(rr)
        return user.id, rr


def _bypass_rate_limit():
    """Return a context manager that makes the token-bucket grant instantly."""
    return patch(
        "app.workers.solicitations.solicitations_bucket",
        return_value=_AlwaysAvailable(),
    )


class _AlwaysAvailable:
    def acquire(self, *, timeout: float = 60.0, poll_interval: float = 0.1) -> bool:
        return True

    def try_acquire(self) -> bool:
        return True


# ---------- happy path ----------

async def test_worker_happy_path(client: AsyncClient) -> None:
    _user_id, rr = await _setup_user_order_and_creds(client)

    fake_payload = {"messageId": "abc-123"}
    with _bypass_rate_limit(), patch(
        "app.workers.solicitations.sp_api_client.call_solicitations",
        return_value=fake_payload,
    ):
        send_solicitation(str(rr.id))

    async with SessionLocal() as session:
        refreshed = await session.get(ReviewRequest, rr.id)
        assert refreshed is not None
        assert refreshed.status == "sent"
        assert refreshed.error_code is None
        assert (refreshed.api_response or {}).get("payload") == fake_payload


# ---------- retry on 429 ----------

async def test_worker_retries_on_rate_limit_then_succeeds(
    client: AsyncClient,
) -> None:
    _user_id, rr = await _setup_user_order_and_creds(client)

    call_count = {"n": 0}

    class FakeRateLimit(Exception):
        pass
    FakeRateLimit.__name__ = "SellingApiRequestException"

    def flaky(*_a, **_kw):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise FakeRateLimit("throttled (429)")
        return {"messageId": "ok"}

    with _bypass_rate_limit(), patch(
        "app.workers.solicitations.sp_api_client.call_solicitations",
        side_effect=flaky,
    ):
        send_solicitation(str(rr.id))

    async with SessionLocal() as session:
        refreshed = await session.get(ReviewRequest, rr.id)
        assert refreshed is not None
        assert refreshed.status == "sent"
        assert call_count["n"] == 2


# ---------- permanent failure ----------

async def test_worker_permanent_failure(client: AsyncClient) -> None:
    _user_id, rr = await _setup_user_order_and_creds(client)

    class FakeBadRequest(Exception):
        pass
    FakeBadRequest.__name__ = "SellingApiBadRequestException"

    def boom(*_a, **_kw):
        raise FakeBadRequest("Order not eligible — order was cancelled")

    with _bypass_rate_limit(), patch(
        "app.workers.solicitations.sp_api_client.call_solicitations",
        side_effect=boom,
    ):
        send_solicitation(str(rr.id))

    async with SessionLocal() as session:
        refreshed = await session.get(ReviewRequest, rr.id)
        assert refreshed is not None
        assert refreshed.status == "failed"
        assert refreshed.error_code == "INELIGIBLE_ORDER"


# ---------- already-solicited mapped to sent ----------

async def test_worker_already_solicited_is_treated_as_sent(
    client: AsyncClient,
) -> None:
    _user_id, rr = await _setup_user_order_and_creds(client)

    class FakeBadRequest(Exception):
        pass
    FakeBadRequest.__name__ = "SellingApiBadRequestException"

    def boom(*_a, **_kw):
        raise FakeBadRequest(
            "Solicitation has already been requested for this order"
        )

    with _bypass_rate_limit(), patch(
        "app.workers.solicitations.sp_api_client.call_solicitations",
        side_effect=boom,
    ):
        send_solicitation(str(rr.id))

    async with SessionLocal() as session:
        refreshed = await session.get(ReviewRequest, rr.id)
        assert refreshed is not None
        assert refreshed.status == "sent"
        assert refreshed.error_code == "ALREADY_SOLICITED_BY_AMAZON"


# ---------- rate-limit smoke ----------

def test_token_bucket_caps_burst_to_five() -> None:
    """5 quick acquires succeed; the 6th doesn't until ~1s later. Uses the
    real Redis from docker-compose with a test-scoped key."""
    from app.services.rate_limit import TokenBucket
    from app.core.queue import _redis_connection

    redis = _redis_connection()
    key = f"test:bucket:{uuid.uuid4().hex[:8]}"
    bucket = TokenBucket(redis, key, max_tokens=5, refill_rate=1.0)
    grants = [bucket.try_acquire() for _ in range(6)]
    redis.delete(key)
    assert grants[:5] == [True, True, True, True, True]
    assert grants[5] is False
