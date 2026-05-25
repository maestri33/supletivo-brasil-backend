"""Smoke dos endpoints de saude."""


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "candidate"


async def test_ready(client):
    resp = await client.get("/ready")
    assert resp.status_code == 200


async def test_status(client):
    resp = await client.get("/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "candidate"
    assert "uptime_seconds" in body
