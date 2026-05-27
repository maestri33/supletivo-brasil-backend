"""Tests for /health/integration auth (COD-91).

Verifies:
  - Without X-Internal-Api-Key → 401
  - With wrong key → 401
  - With correct key → 200 (mocked verification)
  - When INTERNAL_API_KEY not configured → 503 (fail-closed)
"""

from __future__ import annotations

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from app.main import app

TEST_API_KEY = "test-internal-api-key-for-tests"
INTEGRATION_URL = "/api/v1/demilitarized/health/integration"
INFINITEPAY_BASE = "https://api.checkout.infinitepay.io"


@pytest.fixture
def mock_infinitepay():
    with respx.mock(base_url=INFINITEPAY_BASE) as rsps:
        rsps.get("/").mock(return_value=Response(404, json={"error": "not found"}))
        rsps.post("/links").mock(
            return_value=Response(200, json={
                "success": True,
                "url": "https://pay.infinitepay.io/test/abc123",
                "checkout_url": "https://pay.infinitepay.io/test/abc123",
            })
        )
        rsps.post("/payment_check").mock(
            return_value=Response(200, json={"success": True, "paid": False})
        )
        yield rsps


class TestIntegrationHealthAuth:
    async def test_no_api_key_returns_401(self, client: AsyncClient):
        """Request without X-Internal-Api-Key should be rejected."""
        resp = await client.get(INTEGRATION_URL)
        assert resp.status_code == 401
        assert "X-Internal-Api-Key" in resp.json()["detail"]

    async def test_wrong_api_key_returns_401(self, client: AsyncClient):
        """Request with wrong key should be rejected."""
        resp = await client.get(
            INTEGRATION_URL,
            headers={"X-Internal-Api-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    async def test_correct_api_key_returns_200(
        self, client: AsyncClient, mock_infinitepay
    ):
        """Request with correct key should reach the endpoint."""
        resp = await client.get(
            INTEGRATION_URL,
            headers={"X-Internal-Api-Key": TEST_API_KEY},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert len(data["checks"]) == 3

    async def test_fail_closed_when_no_key_configured(
        self, client: AsyncClient, monkeypatch
    ):
        """When INTERNAL_API_KEY is not set, endpoint returns 503 (fail-closed)."""
        monkeypatch.setattr(
            "app.api.deps.get_settings",
            lambda: type("S", (), {"internal_api_key": ""})(),
        )
        # Clear lru_cache so monkeypatch takes effect
        from app.config import get_settings
        get_settings.cache_clear()

        resp = await client.get(
            INTEGRATION_URL,
            headers={"X-Internal-Api-Key": "anything"},
        )
        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"].lower()

        # Restore
        get_settings.cache_clear()

    async def test_old_path_no_longer_works(self, client: AsyncClient):
        """Old /health/integration path (no prefix) should 404."""
        resp = await client.get("/health/integration")
        assert resp.status_code == 404
