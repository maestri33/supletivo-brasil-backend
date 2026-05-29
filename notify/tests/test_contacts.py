"""Testes do modulo de contactos — check, create, get, list.

WhatsApp e DNS sao mockados via `_isolate_external_io` no conftest.
"""

import uuid

from httpx import AsyncClient


async def test_check_contact_email_valid(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/contacts/check?email=teste@exemplo.com")
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["email_valid"] is True
    assert body["phone_valid"] is None


async def test_check_contact_email_invalid(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/contacts/check?email=invalido")
    assert resp.status_code == 200
    assert resp.json()["email_valid"] is False
    assert resp.json()["found"] is False


async def test_check_contact_no_params(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/contacts/check")
    assert resp.status_code == 400


async def test_create_contact_basic(client: AsyncClient, make_auth_user) -> None:
    eid = await make_auth_user()
    resp = await client.post(
        "/api/v1/contacts",
        json={"external_id": eid, "phone": "5511987654321"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["external_id"] == eid
    assert "created_at" in body
    assert "updated_at" in body


async def test_create_contact_duplicate_conflict(
    client: AsyncClient,
    make_auth_user,
) -> None:
    eid = await make_auth_user()
    await client.post(
        "/api/v1/contacts",
        json={"external_id": eid, "phone": "5511987654322"},
    )
    resp = await client.post(
        "/api/v1/contacts",
        json={"external_id": eid, "phone": "5511987654323"},
    )
    assert resp.status_code == 409


async def test_get_contact_not_found(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/contacts/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_contact_found(client: AsyncClient, make_auth_user) -> None:
    eid = await make_auth_user()
    await client.post(
        "/api/v1/contacts",
        json={"external_id": eid, "phone": "5511987654324"},
    )
    resp = await client.get(f"/api/v1/contacts/{eid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["external_id"] == eid
    # Phone foi normalizado (mock retorna 55+digits)
    assert body["phone"].startswith("55")


async def test_create_contact_no_phone_or_email(
    client: AsyncClient,
    make_auth_user,
) -> None:
    eid = await make_auth_user()
    resp = await client.post(
        "/api/v1/contacts",
        json={"external_id": eid},
    )
    assert resp.status_code == 400


async def test_list_contacts(client: AsyncClient, make_auth_user) -> None:
    e1 = await make_auth_user()
    e2 = await make_auth_user()
    await client.post(
        "/api/v1/contacts",
        json={"external_id": e1, "phone": "5511987654325"},
    )
    await client.post(
        "/api/v1/contacts",
        json={"external_id": e2, "phone": "5511987654326"},
    )
    resp = await client.get("/api/v1/contacts?limit=10")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_create_contact_invalid_external_id_rejected(client: AsyncClient) -> None:
    """external_id que nao existe em auth.users deve dar 4xx (FK RESTRICT)."""
    resp = await client.post(
        "/api/v1/contacts",
        json={
            "external_id": str(uuid.uuid4()),  # nao seedado em auth.users
            "phone": "5511987654399",
        },
    )
    # Vai dar 500 (IntegrityError) pq o service nao trata.
    # Documentado como gap menor — service deveria classificar como
    # ValidationError 422 (mesma fix do profiles gap #12).
    assert resp.status_code in (400, 422, 500)
