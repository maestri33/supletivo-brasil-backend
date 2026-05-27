"""Testes E2E do agregado de matrícula (Abertura — milestone 1).

Cobre: criação do Enrollment no webhook `lead.completed`, idempotência por
external_id, leitura via GET e bloqueio por external_id desconhecido (FK).
"""

from uuid import uuid4

from httpx import AsyncClient


async def test_webhook_creates_enrollment(client: AsyncClient, make_auth_user) -> None:
    eid = await make_auth_user()
    promo = str(uuid4())

    resp = await client.post(
        f"/api/v1/webhook/new/{eid}",
        json={"promoter_external_id": promo, "event": "lead.completed"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "started"
    assert "enrollment_id" in body

    got = await client.get(f"/api/v1/enrollments/{eid}")
    assert got.status_code == 200
    data = got.json()
    assert data["external_id"] == eid
    assert data["status"] == "started"
    assert data["promoter_external_id"] == promo
    assert data["hub_external_id"] is None


async def test_enrollment_idempotent(client: AsyncClient, make_auth_user) -> None:
    eid = await make_auth_user()
    payload = {"promoter_external_id": str(uuid4()), "event": "lead.completed"}

    r1 = await client.post(f"/api/v1/webhook/new/{eid}", json=payload)
    r2 = await client.post(f"/api/v1/webhook/new/{eid}", json=payload)

    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r2.json().get("already_exists") is True
    # mesma matrícula nas duas chamadas — não duplicou
    assert r1.json()["enrollment_id"] == r2.json()["enrollment_id"]


async def test_get_enrollment_404(client: AsyncClient) -> None:
    ghost = str(uuid4())
    resp = await client.get(f"/api/v1/enrollments/{ghost}")
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


async def test_unknown_user_creates_no_enrollment(client: AsyncClient) -> None:
    ghost = str(uuid4())  # não existe em auth.users

    resp = await client.post(f"/api/v1/webhook/new/{ghost}", json={"event": "lead.completed"})
    assert resp.status_code == 409

    got = await client.get(f"/api/v1/enrollments/{ghost}")
    assert got.status_code == 404  # nada criado (FK barrou)
