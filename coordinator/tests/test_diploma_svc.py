"""Tests for diploma service CRUD operations."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diploma import DiplomaStatus
from app.services import (
    create_diploma,
    graduate_student,
    list_diplomas,
)


class TestCreateDiploma:
    async def test_creates_diploma(self, db_session: AsyncSession) -> None:
        s_id, c_id = str(uuid4()), str(uuid4())
        diploma = await create_diploma(
            db_session,
            student_external_id=s_id,
            coordinator_external_id=c_id,
        )
        assert diploma.id is not None
        assert diploma.student_external_id == s_id
        assert diploma.coordinator_external_id == c_id
        assert diploma.status == DiplomaStatus.PENDING.value

    async def test_flushes_with_id(self, db_session: AsyncSession) -> None:
        s_id, c_id = str(uuid4()), str(uuid4())
        diploma = await create_diploma(
            db_session,
            student_external_id=s_id,
            coordinator_external_id=c_id,
        )
        assert diploma.id is not None


class TestGraduateStudent:
    async def test_graduates_student(self, db_session: AsyncSession) -> None:
        s_id, c_id = str(uuid4()), str(uuid4())
        diploma = await create_diploma(db_session, student_external_id=s_id, coordinator_external_id=c_id)
        await db_session.commit()

        result = await graduate_student(
            db_session, diploma.id,
            diploma_photo_path="/photos/diploma.jpg",
        )
        assert result is not None
        assert result.status == DiplomaStatus.GRADUATED.value
        assert result.diploma_photo_path == "/photos/diploma.jpg"
        assert result.graduated_at is not None

    async def test_with_history(self, db_session: AsyncSession) -> None:
        s_id, c_id = str(uuid4()), str(uuid4())
        diploma = await create_diploma(db_session, student_external_id=s_id, coordinator_external_id=c_id)
        await db_session.commit()

        result = await graduate_student(
            db_session, diploma.id,
            diploma_photo_path="/photos/hist.jpg",
            history_path="/history/grade.pdf",
            notes="Honorable mention",
        )
        assert result is not None
        assert result.history_path == "/history/grade.pdf"
        assert result.notes == "Honorable mention"

    async def test_returns_none_for_missing(self, db_session: AsyncSession) -> None:
        result = await graduate_student(db_session, "no-such", diploma_photo_path="/p.jpg")
        assert result is None


class TestListDiplomas:
    async def test_returns_all(self, db_session: AsyncSession) -> None:
        s1, s2, c = str(uuid4()), str(uuid4()), str(uuid4())
        await create_diploma(db_session, student_external_id=s1, coordinator_external_id=c)
        await create_diploma(db_session, student_external_id=s2, coordinator_external_id=c)
        await db_session.commit()

        items, total = await list_diplomas(db_session)
        assert total == 2

    async def test_filters_by_student(self, db_session: AsyncSession) -> None:
        s1, s2, c = str(uuid4()), str(uuid4()), str(uuid4())
        await create_diploma(db_session, student_external_id=s1, coordinator_external_id=c)
        await create_diploma(db_session, student_external_id=s2, coordinator_external_id=c)
        await db_session.commit()

        items, total = await list_diplomas(db_session, student_external_id=s1)
        assert total == 1

    async def test_returns_empty(self, db_session: AsyncSession) -> None:
        items, total = await list_diplomas(db_session)
        assert total == 0
