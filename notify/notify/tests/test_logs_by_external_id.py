"""Testes da timeline GET /api/v1/logs/by-external-id/{eid}."""

import uuid

from httpx import AsyncClient


async def test_timeline_empty_for_unknown_external_id(client: AsyncClient) -> None:
    eid = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/logs/by-external-id/{eid}")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_timeline_returns_contact_creation_log(
    client: AsyncClient, make_auth_user,
) -> None:
    eid = await make_auth_user()
    create = await client.post(
        "/api/v1/contacts",
        json={"external_id": eid, "phone": "5511987654321"},
    )
    assert create.status_code == 201

    resp = await client.get(f"/api/v1/logs/by-external-id/{eid}")
    assert resp.status_code == 200
    rows = resp.json()
    actions = {r["action"] for r in rows}
    assert "contact.created" in actions

    # external_id populado direto no log
    for row in rows:
        if row["action"] == "contact.created":
            assert row["external_id"] == eid


async def test_timeline_rejects_invalid_uuid(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/logs/by-external-id/not-a-uuid")
    assert resp.status_code == 422
