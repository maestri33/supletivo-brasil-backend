"""GET /me/pending-items — escopo minimo: status + docs reprovados."""

from httpx import AsyncClient

_HEADERS = {"Authorization": "Bearer test"}


async def test_pending_lists_status(client: AsyncClient, auth_as, make_student) -> None:
    from app.models import StudentStatus

    student = await make_student(status=StudentStatus.AWAITING_DOCUMENTS)
    auth_as(external_id=student.external_id, roles=["student"])
    resp = await client.get(
        "/api/v1/authenticated/students/me/pending-items", headers=_HEADERS
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "awaiting_documents"
    assert body["rejected_documents"] == []
