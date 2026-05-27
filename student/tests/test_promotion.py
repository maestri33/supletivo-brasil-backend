"""Testes do Milestone 1 — promocao (coordenador) e consulta (aluno)."""

from uuid import uuid4

from httpx import AsyncClient

_HEADERS = {"Authorization": "Bearer test"}


async def test_coordinator_promotes_student(client: AsyncClient, auth_as):
    external_id = uuid4()
    auth_as(external_id=uuid4(), roles=["coordinator"])
    resp = await client.post(
        "/api/v1/authenticated/students",
        json={"external_id": str(external_id), "study_platform": {"turma": "2026A"}},
        headers=_HEADERS,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["external_id"] == str(external_id)
    assert data["status"] == "awaiting_documents"
    assert data["study_platform"] == {"turma": "2026A"}


async def test_promote_is_idempotent_conflict(client: AsyncClient, auth_as):
    external_id = uuid4()
    auth_as(external_id=uuid4(), roles=["coordinator"])
    payload = {"external_id": str(external_id), "study_platform": {}}
    first = await client.post("/api/v1/authenticated/students", json=payload, headers=_HEADERS)
    assert first.status_code == 201
    second = await client.post("/api/v1/authenticated/students", json=payload, headers=_HEADERS)
    assert second.status_code == 409
    assert second.json()["code"] == "student_already_exists"


async def test_student_reads_own_data(client: AsyncClient, auth_as):
    external_id = uuid4()
    auth_as(external_id=uuid4(), roles=["coordinator"])
    await client.post(
        "/api/v1/authenticated/students",
        json={"external_id": str(external_id), "study_platform": {}},
        headers=_HEADERS,
    )
    auth_as(external_id=external_id, roles=["student"])
    resp = await client.get("/api/v1/authenticated/students/me", headers=_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["external_id"] == str(external_id)


async def test_get_me_not_found(client: AsyncClient, auth_as):
    auth_as(external_id=uuid4(), roles=["student"])
    resp = await client.get("/api/v1/authenticated/students/me", headers=_HEADERS)
    assert resp.status_code == 404
    assert resp.json()["code"] == "student_not_found"


async def test_wrong_role_forbidden(client: AsyncClient, auth_as):
    auth_as(external_id=uuid4(), roles=["student"])  # aluno tentando promover
    resp = await client.post(
        "/api/v1/authenticated/students",
        json={"external_id": str(uuid4()), "study_platform": {}},
        headers=_HEADERS,
    )
    assert resp.status_code == 403
