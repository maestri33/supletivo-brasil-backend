"""Testes das rotas desmilitarizadas (listar/filtrar/buscar candidatos)."""

from uuid import uuid4


async def test_list_and_filter_by_hub(client, make_candidate):
    hub = uuid4()
    e1 = await make_candidate(status="captured", hub=hub)
    await make_candidate(status="completed")

    resp = await client.get("/api/v1/demilitarized/candidates")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2

    resp = await client.get(f"/api/v1/demilitarized/candidates?hub_external_id={hub}")
    body = resp.json()
    assert body["total"] == 1
    assert body["candidates"][0]["external_id"] == str(e1)


async def test_filter_by_status(client, make_candidate):
    await make_candidate(status="captured")
    await make_candidate(status="completed")
    resp = await client.get("/api/v1/demilitarized/candidates?status=completed")
    assert resp.json()["total"] == 1
    assert resp.json()["candidates"][0]["status"] == "completed"


async def test_get_by_external_id(client, make_candidate):
    ext = await make_candidate(status="captured")
    resp = await client.get(f"/api/v1/demilitarized/candidates/{ext}")
    assert resp.status_code == 200
    assert resp.json()["external_id"] == str(ext)


async def test_get_unknown_returns_404(client):
    resp = await client.get(f"/api/v1/demilitarized/candidates/{uuid4()}")
    assert resp.status_code == 404
