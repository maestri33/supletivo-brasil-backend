"""Testes dos endpoints de saúde (convenção v7m: /health /ready /status)."""

from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "fees"}


async def test_ready(client: AsyncClient) -> None:
    resp = await client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


async def test_status(client: AsyncClient) -> None:
    resp = await client.get("/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "fees"
    assert body["version"] == "0.1.0"
    assert "uptime_seconds" in body
