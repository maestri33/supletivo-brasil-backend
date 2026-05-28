"""Diploma — coord emite, aluno faz pickup -> veterano."""

from uuid import uuid4

from httpx import AsyncClient

_HEADERS = {"Authorization": "Bearer test"}


async def test_issue_then_pickup_full_cycle(client: AsyncClient, auth_as, make_student) -> None:
    from app.models import StudentStatus

    student = await make_student(status=StudentStatus.AWAITING_DOCUMENTATION_DISPATCH)

    auth_as(external_id=uuid4(), roles=["coordinator"])
    issue = await client.post(
        f"/api/v1/authenticated/students/{student.id}/diploma/issue",
        headers=_HEADERS,
    )
    assert issue.status_code == 201, issue.text
    assert issue.json()["issued_at"] is not None

    auth_as(external_id=student.external_id, roles=["student"])
    pickup = await client.post(
        "/api/v1/authenticated/students/me/diploma/pickup",
        json={"pickup_photo_external_id": str(uuid4())},
        headers=_HEADERS,
    )
    assert pickup.status_code == 200, pickup.text
    assert pickup.json()["picked_up_at"] is not None

    me = await client.get("/api/v1/authenticated/students/me", headers=_HEADERS)
    assert me.json()["status"] == "veteran"


async def test_pickup_without_issue_blocked(client: AsyncClient, auth_as, make_student) -> None:
    from app.models import StudentStatus

    student = await make_student(status=StudentStatus.EXAM_RELEASED)
    auth_as(external_id=student.external_id, roles=["student"])
    resp = await client.post(
        "/api/v1/authenticated/students/me/diploma/pickup",
        json={"pickup_photo_external_id": str(uuid4())},
        headers=_HEADERS,
    )
    # gate de status do require_student_with_status devolve 403
    assert resp.status_code == 403
