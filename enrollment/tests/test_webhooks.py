"""Testes E2E do receptor de webhook contra Postgres real (sem mock).

Cobre: persistência + payload JSONB, idempotência por (external_id, event),
FK cross-schema p/ auth.users, e os endpoints de auditoria.
"""

from uuid import uuid4

from httpx import AsyncClient


async def test_receive_persists_event(client: AsyncClient, make_auth_user) -> None:
    eid = await make_auth_user()
    promo = str(uuid4())

    resp = await client.post(
        f"/api/v1/webhook/new/{eid}",
        json={"promoter_external_id": promo, "event": "lead.completed"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["ok"] is True
    assert body["event"] == "lead.completed"
    assert isinstance(body["id"], int)

    listing = await client.get(f"/api/v1/events?external_id={eid}")
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 1
    assert items[0]["external_id"] == eid
    assert items[0]["event"] == "lead.completed"
    assert items[0]["promoter_external_id"] == promo
    # payload bruto preservado em JSONB
    assert items[0]["payload"] == {
        "promoter_external_id": promo,
        "event": "lead.completed",
    }


async def test_idempotent_same_event(client: AsyncClient, make_auth_user) -> None:
    eid = await make_auth_user()
    payload = {"promoter_external_id": str(uuid4()), "event": "lead.completed"}

    r1 = await client.post(f"/api/v1/webhook/new/{eid}", json=payload)
    r2 = await client.post(f"/api/v1/webhook/new/{eid}", json=payload)

    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json().get("already_exists") is True

    listing = await client.get(f"/api/v1/events?external_id={eid}")
    assert len(listing.json()) == 1  # não duplicou


async def test_different_event_creates_new_row(client: AsyncClient, make_auth_user) -> None:
    eid = await make_auth_user()
    await client.post(f"/api/v1/webhook/new/{eid}", json={"event": "lead.completed"})
    await client.post(f"/api/v1/webhook/new/{eid}", json={"event": "lead.reopened"})

    listing = await client.get(f"/api/v1/events?external_id={eid}")
    assert len(listing.json()) == 2  # dedup é por (external_id, event)


async def test_unknown_user_returns_409(client: AsyncClient) -> None:
    ghost = str(uuid4())  # não existe em auth.users
    resp = await client.post(f"/api/v1/webhook/new/{ghost}", json={"event": "lead.completed"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "UNKNOWN_EXTERNAL_ID"

    listing = await client.get(f"/api/v1/events?external_id={ghost}")
    assert listing.json() == []  # nada persistido (FK barrou)


async def test_get_event_by_id_and_404(client: AsyncClient, make_auth_user) -> None:
    eid = await make_auth_user()
    created = await client.post(f"/api/v1/webhook/new/{eid}", json={"event": "lead.completed"})
    new_id = created.json()["id"]

    got = await client.get(f"/api/v1/events/{new_id}")
    assert got.status_code == 200
    assert got.json()["id"] == new_id

    missing = await client.get("/api/v1/events/999999")
    assert missing.status_code == 404
    assert missing.json()["code"] == "NOT_FOUND"
