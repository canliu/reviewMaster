"""SP-API credentials endpoint tests (per-shop model). The SP-API client
itself is mocked at the `app.services.sp_api_client` seam."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import engine
from app.main import app

TEST_PW = "letter1-letter2"  # pragma: allowlist secret
US_MARKETPLACE = "ATVPDKIKX0DER"
CA_MARKETPLACE = "A2EUQ1WTGCTBG2"


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


def _body(shop_site: str = "p3:US", marketplace_id: str = US_MARKETPLACE) -> dict:
    return {
        "shop_site": shop_site,
        "lwa_client_id": "amzn1.application-oa2-client.fake",
        "lwa_client_secret": "fake-secret",  # pragma: allowlist secret
        "refresh_token": "Atzr|FAKE-REFRESH-TOKEN",
        "selling_partner_id": "A1FAKE",
        "marketplace_id": marketplace_id,
    }


# ---------- save / fetch ----------

async def test_save_and_list_never_exposes_secrets(client: AsyncClient) -> None:
    token = await _register(client)

    save_resp = await client.post(
        "/api/sp-api/credentials", headers=_auth(token), json=_body()
    )
    assert save_resp.status_code == 201, save_resp.text
    body = save_resp.json()
    assert body["configured"] is True
    assert body["shop_site"] == "p3:US"
    assert "lwa_client_secret" not in body
    assert "refresh_token" not in body

    list_resp = await client.get(
        "/api/sp-api/credentials", headers=_auth(token)
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    item = items[0]
    assert item["shop_site"] == "p3:US"
    assert item["marketplace_id"] == US_MARKETPLACE
    assert item["marketplace_label"].startswith("Amazon.com")
    assert "secret" not in item
    assert "refresh_token" not in item


async def test_list_empty_when_not_configured(client: AsyncClient) -> None:
    token = await _register(client)
    resp = await client.get("/api/sp-api/credentials", headers=_auth(token))
    assert resp.json() == {"items": []}


async def test_save_multiple_shops(client: AsyncClient) -> None:
    token = await _register(client)
    await client.post(
        "/api/sp-api/credentials",
        headers=_auth(token),
        json=_body(shop_site="p3:US", marketplace_id=US_MARKETPLACE),
    )
    await client.post(
        "/api/sp-api/credentials",
        headers=_auth(token),
        json=_body(shop_site="p3:CA", marketplace_id=CA_MARKETPLACE),
    )
    resp = await client.get("/api/sp-api/credentials", headers=_auth(token))
    items = resp.json()["items"]
    assert {it["shop_site"] for it in items} == {"p3:US", "p3:CA"}


async def test_save_rejects_bad_marketplace(client: AsyncClient) -> None:
    token = await _register(client)
    bad = {**_body(), "marketplace_id": "NOT-A-MARKETPLACE"}
    resp = await client.post(
        "/api/sp-api/credentials", headers=_auth(token), json=bad
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "UNSUPPORTED_MARKETPLACE"


# ---------- test-connection (per shop) ----------

async def test_connection_ok(client: AsyncClient) -> None:
    token = await _register(client)
    await client.post(
        "/api/sp-api/credentials", headers=_auth(token), json=_body()
    )
    fake_payload = [
        {"marketplace": {"id": US_MARKETPLACE, "name": "Amazon.com"}},
        {"marketplace": {"id": CA_MARKETPLACE, "name": "Amazon.ca"}},
    ]
    with patch(
        "app.api.sp_api.sp_api_client.call_marketplace_participations",
        return_value=fake_payload,
    ):
        resp = await client.post(
            "/api/sp-api/credentials/p3:US/test-connection",
            headers=_auth(token),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert US_MARKETPLACE in body["marketplaces"]


async def test_connection_rejected_refresh_token(client: AsyncClient) -> None:
    token = await _register(client)
    await client.post(
        "/api/sp-api/credentials", headers=_auth(token), json=_body()
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
            "/api/sp-api/credentials/p3:US/test-connection",
            headers=_auth(token),
        )
    body = resp.json()
    assert body["ok"] is False
    assert body["error_code"] == "INVALID_REFRESH_TOKEN"


# ---------- disconnect ----------

async def test_delete_credentials_per_shop(client: AsyncClient) -> None:
    token = await _register(client)
    await client.post(
        "/api/sp-api/credentials",
        headers=_auth(token),
        json=_body(shop_site="p3:US"),
    )
    await client.post(
        "/api/sp-api/credentials",
        headers=_auth(token),
        json=_body(shop_site="p3:CA", marketplace_id=CA_MARKETPLACE),
    )
    deleted = await client.delete(
        "/api/sp-api/credentials/p3:US", headers=_auth(token)
    )
    assert deleted.status_code == 204
    list_resp = await client.get(
        "/api/sp-api/credentials", headers=_auth(token)
    )
    items = list_resp.json()["items"]
    assert [it["shop_site"] for it in items] == ["p3:CA"]
