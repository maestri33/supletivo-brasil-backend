"""Testes do /status (root) enriquecido + /api/v1/logs/metrics."""

from httpx import AsyncClient


async def test_status_root_returns_metrics_block(client: AsyncClient) -> None:
    resp = await client.get("/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "uptime_seconds" in body
    assert "metrics" in body

    metrics = body["metrics"]
    # Snapshot inicial — DB recem criado, so o seed default existe
    assert metrics["contacts"] == 0
    assert metrics["templates_active"] >= 1
    assert metrics["messages"]["total"] == 0
    assert "whatsapp_by_status" in metrics["messages"]
    assert "email_by_status" in metrics["messages"]
    assert isinstance(metrics["recent_errors"], list)


async def test_status_metrics_endpoint_with_window(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/logs/metrics?window_hours=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["window_hours"] == 1
    assert "messages" in body
    assert "recent_errors" in body


async def test_status_metrics_rejects_out_of_range_window(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/logs/metrics?window_hours=10000")
    assert resp.status_code == 422

    resp2 = await client.get("/api/v1/logs/metrics?window_hours=0")
    assert resp2.status_code == 422
