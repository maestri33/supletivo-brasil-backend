"""Documentos do aluno — submissao, listagem e submit-for-review."""

from uuid import uuid4

from httpx import AsyncClient

from app.models import StudentStatus

_HEADERS = {"Authorization": "Bearer test"}


async def test_submit_document_and_list(client: AsyncClient, auth_as, make_student) -> None:
    student = await make_student(status=StudentStatus.AWAITING_DOCUMENTS)
    auth_as(external_id=student.external_id, roles=["student"])

    payload = {"document_type": "id_card", "document_external_id": str(uuid4())}
    resp = await client.post(
        "/api/v1/authenticated/students/me/documents", json=payload, headers=_HEADERS
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["document_type"] == "id_card"

    listing = await client.get(
        "/api/v1/authenticated/students/me/documents", headers=_HEADERS
    )
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    assert body["items"][0]["document_type"] == "id_card"


async def test_submit_duplicate_document_conflicts(
    client: AsyncClient, auth_as, make_student
) -> None:
    from app.models import StudentStatus

    student = await make_student(status=StudentStatus.AWAITING_DOCUMENTS)
    auth_as(external_id=student.external_id, roles=["student"])

    payload = {"document_type": "id_card", "document_external_id": str(uuid4())}
    first = await client.post(
        "/api/v1/authenticated/students/me/documents", json=payload, headers=_HEADERS
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/authenticated/students/me/documents", json=payload, headers=_HEADERS
    )
    assert second.status_code == 409
    assert second.json()["code"] == "student_document_already_exists"


async def test_submit_for_review_requires_obligatorios(
    client: AsyncClient, auth_as, make_student
) -> None:
    from app.models import StudentStatus

    student = await make_student(status=StudentStatus.AWAITING_DOCUMENTS)
    auth_as(external_id=student.external_id, roles=["student"])

    resp = await client.post(
        "/api/v1/authenticated/students/me/documents/submit-for-review",
        headers=_HEADERS,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "required_document_missing"


async def test_submit_for_review_advances_status(
    client: AsyncClient, auth_as, make_student
) -> None:
    from app.models import StudentStatus

    student = await make_student(status=StudentStatus.AWAITING_DOCUMENTS)
    auth_as(external_id=student.external_id, roles=["student"])

    for doc_type in ("certificate", "transcript", "id_card"):
        resp = await client.post(
            "/api/v1/authenticated/students/me/documents",
            json={"document_type": doc_type, "document_external_id": str(uuid4())},
            headers=_HEADERS,
        )
        assert resp.status_code == 201, resp.text

    resp = await client.post(
        "/api/v1/authenticated/students/me/documents/submit-for-review",
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    me = await client.get("/api/v1/authenticated/students/me", headers=_HEADERS)
    assert me.json()["status"] == "documents_under_review"
