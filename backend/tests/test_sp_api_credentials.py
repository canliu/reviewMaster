"""SP-API credentials endpoint tests. The SP-API client itself is mocked at
the `app.services.sp_api_client` seam."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import engine
from app.main import app

TEST_PW = "letter1-letter2"  # pragma: allowlist secret
US_MARKETPLACE = "ATVPDKIKX0DER"


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def _register(client: AsyncClient) -> str:
    email = f"test-{uuid.uuid4().hex[:10]}@example.com"
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PW}
    )
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


VALID_BODY = {
    "lwa_client_id": "amzn1.application-oa2-client.fake",
    "lwa_client_secret": "fake-secret",  # pragma: allowlist secret
    "refresh_token": "Atzr|FAKE-REFRESH-TOKEN",
    "selling_partner_id": "A1FAKE",
    "marketplace_id": US_MARKETPLACE,
}


# ---------- save / fetch ----------

async def test_save_and_fetch_metadata_never_exposes_secrets(
    client: AsyncClient,
) -> None:
    token = await _register(client)

    save_resp = await client.post(
        "/api/sp-api/credentials", headers=_auth(token), json=VALID_BODY
    )
    assert save_resp.status_code == 201, save_resp.text
    body = save_resp.json()
    assert body["configured"] is True
    # Never echo the secrets back.
    assert "lwa_client_secret" not in body
    assert "refresh_token" not in body

    get_resp = await client.get(
        "/api/sp-api/credentials", headers=_auth(token)
    )
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["configured"] is True
    assert body["marketplace_id"] == US_MARKETPLACE
    assert body["marketplace_label"].startswith("Amazon.com")
    assert "secret" not in body
    assert "refresh_token" not in body


async def test_get_when_not_configured(client: AsyncClient) -> None:
    token = await _register(client)
    resp = await client.get("/api/sp-api/credentials", headers=_auth(token))
    assert resp.json() == {
        "configured": False,
        "lwa_client_id_prefix": None,
        "selling_partner_id": None,
        "marketplace_id": None,
        "marketplace_label": None,
        "updated_at": None,
    }


async def test_save_rejects_bad_marketplace(client: AsyncClient) -> None:
    token = await _register(client)
    bad = {**VALID_BODY, "marketplace_id": "NOT-A-MARKETPLACE"}
    resp = await client.post(
        "/api/sp-api/credentials", headers=_auth(token), json=bad
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "UNSUPPORTED_MARKETPLACE"


# ---------- test-connection ----------

async def test_connection_ok(client: AsyncClient) -> None:
    token = await _register(client)
    await client.post(
        "/api/sp-api/credentials", headers=_auth(token), json=VALID_BODY
    )
    fake_payload = [
        {"marketplace": {"id": US_MARKETPLACE, "name": "Amazon.com"}},
        {"marketplace": {"id": "A2EUQ1WTGCTBG2", "name": "Amazon.ca"}},
    ]
    with patch(
        "app.api.sp_api.sp_api_client.call_marketplace_participations",
        return_value=fake_payload,
    ):
        resp = await client.post(
            "/api/sp-api/test-connection", headers=_auth(token)
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert US_MARKETPLACE in body["marketplaces"]
    assert body["elapsed_ms"] >= 0


async def test_connection_rejected_refresh_token(client: AsyncClient) -> None:
    token = await _register(client)
    await client.post(
        "/api/sp-api/credentials", headers=_auth(token), json=VALID_BODY
    )

    class FakeUnauthorized(Exception):
        pass
    FakeUnauthorized.__name__ = "SellingApiUnauthorizedException"

    def boom(*_a, **_kw):
        raise FakeUnauthorized("Refresh token rejected")

    with patch(
        "app.api.sp_api.sp_api_client.call_marketplace_participations",
        side_effect=boom,
    ):
        resp = await client.post(
            "/api/sp-api/test-connection", headers=_auth(token)
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error_code"] == "INVALID_REFRESH_TOKEN"


# ---------- disconnect ----------

async def test_delete_credentials(client: AsyncClient) -> None:
    token = await _register(client)
    await client.post(
        "/api/sp-api/credentials", headers=_auth(token), json=VALID_BODY
    )
    deleted = await client.delete(
        "/api/sp-api/credentials", headers=_auth(token)
    )
    assert deleted.status_code == 204
    fetched = await client.get(
        "/api/sp-api/credentials", headers=_auth(token)
    )
    assert fetched.json()["configured"] is False
