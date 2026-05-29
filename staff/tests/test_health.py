"""Testes dos endpoints de saude (convencao: /health /ready /status)."""

from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "staff"}


async def test_status(client: AsyncClient) -> None:
    resp = await client.get("/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "staff"
    assert body["version"] == "0.1.0"
    assert "uptime_seconds" in body


async def test_ready_degraded(client: AsyncClient) -> None:
    """Sem DB real, /ready retorna status degradado (nao 500)."""
    resp = await client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["db"] == "unreachable"
