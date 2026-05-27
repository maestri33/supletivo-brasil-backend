async def test_health_endpoint(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "webhook_security" in data
    assert isinstance(data["webhook_security"], dict)
    assert "webhook_hmac_configured" in data["webhook_security"]


async def test_ready_endpoint(client):
    r = await client.get("/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    # ready endpoint nao preenche webhook_security (usa webhook_security_configured internamente)
