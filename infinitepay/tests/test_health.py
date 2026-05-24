async def test_health_endpoint(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_ready_endpoint(client):
    r = await client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
