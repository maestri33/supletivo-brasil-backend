"""Testes para health/readiness endpoints do lead service."""

import pytest


@pytest.mark.asyncio
class TestHealthEndpoints:
    """Endpoints de health check — sem autenticacao."""

    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "lead"

    async def test_ready(self, client):
        resp = await client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "ready")

    async def test_status(self, client):
        resp = await client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
class TestRootNotFound:
    """Rotas inexistentes retornam 404."""

    async def test_root_404(self, client):
        resp = await client.get("/")
        assert resp.status_code == 404

    async def test_random_path_404(self, client):
        resp = await client.get("/api/v1/nonexistent")
        assert resp.status_code == 404
