"""Testes /, /health e /ready."""

from httpx import AsyncClient


async def test_root_has_metadata(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "profiles-service"
    assert body["version"] == "0.3.0"
    assert body["env"] in ("dev", "prod")
    assert body["status"] == "ok"
    assert "uptime_seconds" in body
    assert isinstance(body["uptime_seconds"], (int, float))


async def test_root_database_ok(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"]["status"] == "ok"


async def test_root_has_integrations_key(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "integrations" in body
    assert isinstance(body["integrations"], dict)


async def test_health_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "profiles-service"


async def test_ready_when_db_up(client: AsyncClient) -> None:
    resp = await client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"
