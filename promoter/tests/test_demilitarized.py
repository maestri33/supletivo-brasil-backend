"""Rotas desmilitarizadas: criacao (coordinator), listagem/busca e validacao de ref."""

from uuid import uuid4


async def test_create_promoter_promotes_role(client, mocks):
    ext = uuid4()
    hub = uuid4()
    resp = await client.post(
        "/api/v1/demilitarized/promoters",
        json={"external_id": str(ext), "hub_external_id": str(hub)},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["external_id"] == str(ext)
    assert body["status"] == "active"
    assert f"ref={ext}" in body["ref_url"]
    # papel candidate -> promoter promovido no roles
    mocks.roles.promote.assert_awaited_once_with(str(ext), "promoter")


async def test_create_promoter_is_idempotent(client, mocks):
    ext = uuid4()
    payload = {"external_id": str(ext)}
    await client.post("/api/v1/demilitarized/promoters", json=payload)
    await client.post("/api/v1/demilitarized/promoters", json=payload)

    resp = await client.get("/api/v1/demilitarized/promoters")
    assert resp.json()["total"] == 1
    # promocao de papel so' na criacao real (1x)
    mocks.roles.promote.assert_awaited_once()


async def test_list_and_filter_by_hub(client, make_promoter):
    hub = uuid4()
    e1 = await make_promoter(hub=hub)
    await make_promoter()

    resp = await client.get("/api/v1/demilitarized/promoters")
    assert resp.json()["total"] == 2

    resp = await client.get(f"/api/v1/demilitarized/promoters?hub_external_id={hub}")
    body = resp.json()
    assert body["total"] == 1
    assert body["promoters"][0]["external_id"] == str(e1)


async def test_get_by_external_id_and_404(client, make_promoter):
    ext = await make_promoter()
    resp = await client.get(f"/api/v1/demilitarized/promoters/{ext}")
    assert resp.status_code == 200
    assert resp.json()["external_id"] == str(ext)

    resp = await client.get(f"/api/v1/demilitarized/promoters/{uuid4()}")
    assert resp.status_code == 404


async def test_validate_ref_active(client, make_promoter):
    hub = uuid4()
    ext = await make_promoter(status="active", hub=hub)
    resp = await client.get(f"/api/v1/demilitarized/validate-ref/{ext}")
    body = resp.json()
    assert body["valid"] is True
    assert body["external_id"] == str(ext)
    assert body["hub_external_id"] == str(hub)


async def test_validate_ref_unknown(client):
    resp = await client.get(f"/api/v1/demilitarized/validate-ref/{uuid4()}")
    assert resp.json()["valid"] is False


async def test_validate_ref_suspended(client, make_promoter):
    ext = await make_promoter(status="suspended")
    resp = await client.get(f"/api/v1/demilitarized/validate-ref/{ext}")
    assert resp.json()["valid"] is False
