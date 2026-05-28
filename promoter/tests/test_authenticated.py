"""Rotas autenticadas: visao do proprio promoter (me, leads, commissions)."""

from uuid import uuid4

from app.exceptions import IntegrationError


async def test_me(client, make_promoter, login_as):
    ext = await make_promoter(status="active")
    login_as(ext)
    resp = await client.get("/api/v1/authenticated/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["external_id"] == str(ext)
    assert f"ref={ext}" in body["ref_url"]


async def test_me_unknown_promoter_404(client, login_as):
    login_as(uuid4())  # autenticado, mas sem registro de promoter
    resp = await client.get("/api/v1/authenticated/me")
    assert resp.status_code == 404


async def test_me_suspended_forbidden(client, make_promoter, login_as):
    ext = await make_promoter(status="suspended")
    login_as(ext)
    resp = await client.get("/api/v1/authenticated/me")
    assert resp.status_code == 403


async def test_my_leads_filters_by_promoter(client, make_promoter, login_as, mocks):
    ext = await make_promoter(status="active")
    other = uuid4()
    login_as(ext)
    mocks.lead.list_by_promoter.return_value = [
        {"external_id": str(uuid4()), "status": "captured", "promoter_external_id": str(ext)},
        {"external_id": str(uuid4()), "status": "completed", "promoter_external_id": str(other)},
    ]
    resp = await client.get("/api/v1/authenticated/me/leads")
    assert resp.status_code == 200
    body = resp.json()
    # so' o lead atribuido a este promoter (filtro defensivo client-side)
    assert body["total"] == 1
    assert body["leads"][0]["status"] == "captured"


async def test_my_commissions_available(client, make_promoter, login_as, mocks):
    ext = await make_promoter(status="active")
    login_as(ext)
    mocks.commissions.list_by_promoter.return_value = [
        {"id": "c1", "status": "pending", "amount": 100.0},
    ]
    resp = await client.get("/api/v1/authenticated/me/commissions")
    body = resp.json()
    assert body["available"] is True
    assert body["total"] == 1


async def test_my_commissions_degrades_when_service_down(client, make_promoter, login_as, mocks):
    ext = await make_promoter(status="active")
    login_as(ext)
    mocks.commissions.list_by_promoter.side_effect = IntegrationError("commissions fora")
    resp = await client.get("/api/v1/authenticated/me/commissions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert body["total"] == 0
