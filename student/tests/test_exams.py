"""Provas do aluno — agendamento (aluno) e correcao (coordenador)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient

_HEADERS = {"Authorization": "Bearer test"}


async def test_schedule_exam_advances_status(client: AsyncClient, auth_as, make_student) -> None:
    from app.models import StudentStatus

    student = await make_student(status=StudentStatus.EXAM_RELEASED)
    auth_as(external_id=student.external_id, roles=["student"])

    payload = {
        "subject": "Matematica",
        "scheduled_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
    }
    resp = await client.post(
        "/api/v1/authenticated/students/me/exams", json=payload, headers=_HEADERS
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["subject"] == "Matematica"
    assert resp.json()["attempt_number"] == 1

    me = await client.get("/api/v1/authenticated/students/me", headers=_HEADERS)
    assert me.json()["status"] == "exam_scheduled"


async def test_grade_passed_advances_to_dispatch(
    client: AsyncClient, auth_as, make_student
) -> None:
    from app.models import StudentStatus

    student = await make_student(status=StudentStatus.EXAM_RELEASED)
    auth_as(external_id=student.external_id, roles=["student"])
    schedule = await client.post(
        "/api/v1/authenticated/students/me/exams",
        json={
            "subject": "Portugues",
            "scheduled_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        },
        headers=_HEADERS,
    )
    exam_id = schedule.json()["id"]

    auth_as(external_id=uuid4(), roles=["coordinator"])
    resp = await client.patch(
        f"/api/v1/authenticated/students/{student.id}/exams/{exam_id}",
        json={"result": "passed", "notes": "muito bom"},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["result"] == "passed"

    auth_as(external_id=student.external_id, roles=["student"])
    me = await client.get("/api/v1/authenticated/students/me", headers=_HEADERS)
    assert me.json()["status"] == "awaiting_documentation_dispatch"


async def test_grade_failed_reopens_for_retry(client: AsyncClient, auth_as, make_student) -> None:
    from app.models import StudentStatus

    student = await make_student(status=StudentStatus.EXAM_RELEASED)
    auth_as(external_id=student.external_id, roles=["student"])
    schedule = await client.post(
        "/api/v1/authenticated/students/me/exams",
        json={
            "subject": "Geografia",
            "scheduled_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        },
        headers=_HEADERS,
    )
    exam_id = schedule.json()["id"]

    auth_as(external_id=uuid4(), roles=["coordinator"])
    resp = await client.patch(
        f"/api/v1/authenticated/students/{student.id}/exams/{exam_id}",
        json={"result": "failed"},
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["result"] == "failed"

    auth_as(external_id=student.external_id, roles=["student"])
    me = await client.get("/api/v1/authenticated/students/me", headers=_HEADERS)
    assert me.json()["status"] == "exam_released"

    # Reagendamento gera tentativa 2
    second = await client.post(
        "/api/v1/authenticated/students/me/exams",
        json={
            "subject": "Geografia",
            "scheduled_at": (datetime.now(UTC) + timedelta(days=4)).isoformat(),
        },
        headers=_HEADERS,
    )
    assert second.status_code == 201
    assert second.json()["attempt_number"] == 2
