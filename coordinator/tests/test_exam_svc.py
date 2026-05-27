"""Tests for exam service CRUD operations."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import ExamStatus
from app.services import (
    create_coordinator,
    create_exam,
    grade_exam,
    list_exams,
    submit_exam,
)


@pytest.fixture
async def coordinator(db_session: AsyncSession) -> str:
    c = await create_coordinator(db_session, external_id="exam-ext", hub_external_id="exam-hub")
    await db_session.commit()
    return c.id


class TestCreateExam:
    async def test_creates_exam(self, db_session: AsyncSession, coordinator: str) -> None:
        exam = await create_exam(
            db_session,
            coordinator_id=coordinator,
            student_external_id="std-ex-001",
            training_external_id="tr-ex-001",
        )
        assert exam.id is not None
        assert exam.coordinator_id == coordinator
        assert exam.student_external_id == "std-ex-001"
        assert exam.training_external_id == "tr-ex-001"
        assert exam.status == ExamStatus.created
        assert exam.max_score == 100

    async def test_custom_max_score(self, db_session: AsyncSession, coordinator: str) -> None:
        exam = await create_exam(
            db_session,
            coordinator_id=coordinator,
            student_external_id="std-ex-002",
            training_external_id="tr-ex-002",
            max_score=50,
        )
        assert exam.max_score == 50


class TestSubmitExam:
    async def test_submits_exam(self, db_session: AsyncSession, coordinator: str) -> None:
        exam = await create_exam(
            db_session, coordinator_id=coordinator,
            student_external_id="std-sub", training_external_id="tr-sub",
        )
        await db_session.commit()

        result = await submit_exam(db_session, exam.id)
        assert result is not None
        assert result.status == ExamStatus.submitted

    async def test_returns_none_for_missing(self, db_session: AsyncSession) -> None:
        result = await submit_exam(db_session, "no-such")
        assert result is None


class TestGradeExam:
    async def test_grades_exam(self, db_session: AsyncSession, coordinator: str) -> None:
        exam = await create_exam(
            db_session, coordinator_id=coordinator,
            student_external_id="std-grade", training_external_id="tr-grade",
        )
        await db_session.commit()

        result = await grade_exam(db_session, exam.id, score=85, notes="Good work")
        assert result is not None
        assert result.score == 85
        assert result.status == ExamStatus.graded
        assert result.result_notes == "Good work"

    async def test_accepts_ai_correction(self, db_session: AsyncSession, coordinator: str) -> None:
        exam = await create_exam(
            db_session, coordinator_id=coordinator,
            student_external_id="std-ai", training_external_id="tr-ai",
        )
        await db_session.commit()

        result = await grade_exam(db_session, exam.id, score=90, ai_correction="Auto-graded OK")
        assert result is not None
        assert result.score == 90
        assert result.ai_correction == "Auto-graded OK"

    async def test_returns_none_for_missing(self, db_session: AsyncSession) -> None:
        result = await grade_exam(db_session, "no-such", score=50)
        assert result is None


class TestListExams:
    async def test_returns_all(self, db_session: AsyncSession, coordinator: str) -> None:
        await create_exam(
            db_session, coordinator_id=coordinator,
            student_external_id="s1", training_external_id="t1",
        )
        await create_exam(
            db_session, coordinator_id=coordinator,
            student_external_id="s2", training_external_id="t2",
        )
        await db_session.commit()

        items, total = await list_exams(db_session)
        assert total == 2

    async def test_filters_by_student(self, db_session: AsyncSession, coordinator: str) -> None:
        await create_exam(
            db_session, coordinator_id=coordinator,
            student_external_id="std-x", training_external_id="t1",
        )
        await create_exam(
            db_session, coordinator_id=coordinator,
            student_external_id="std-y", training_external_id="t2",
        )
        await db_session.commit()

        items, total = await list_exams(db_session, student_external_id="std-x")
        assert total == 1

    async def test_returns_empty(self, db_session: AsyncSession) -> None:
        items, total = await list_exams(db_session)
        assert total == 0
