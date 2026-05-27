"""Tests for student document service CRUD operations."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import (
    create_student_document,
    list_student_documents,
    submit_document_to_institution,
)


@pytest.fixture
def student_id() -> str:
    return str(uuid4())


@pytest.fixture
def coordinator_id() -> str:
    return str(uuid4())


class TestCreateStudentDocument:
    async def test_creates_document(
        self, db_session: AsyncSession, student_id: str, coordinator_id: str
    ) -> None:
        doc = await create_student_document(
            db_session,
            student_external_id=student_id,
            coordinator_external_id=coordinator_id,
            document_type="rg",
            description="Cópia RG",
        )
        assert doc.id is not None
        assert doc.student_external_id == student_id
        assert doc.coordinator_external_id == coordinator_id
        assert doc.document_type == "rg"
        assert doc.description == "Cópia RG"
        assert doc.submitted_to_institution is False

    async def test_optional_file_path(
        self, db_session: AsyncSession, student_id: str, coordinator_id: str
    ) -> None:
        doc = await create_student_document(
            db_session,
            student_external_id=student_id,
            coordinator_external_id=coordinator_id,
            document_type="cpf",
            description="CPF",
            file_path="/tmp/docs/cpf.pdf",
        )
        assert doc.file_path == "/tmp/docs/cpf.pdf"


class TestListStudentDocuments:
    async def test_returns_all(self, db_session: AsyncSession) -> None:
        s1, s2 = str(uuid4()), str(uuid4())
        c = str(uuid4())
        await create_student_document(
            db_session, student_external_id=s1, coordinator_external_id=c,
            document_type="rg", description="RG 1",
        )
        await create_student_document(
            db_session, student_external_id=s2, coordinator_external_id=c,
            document_type="cpf", description="CPF 2",
        )
        await db_session.commit()

        items, total = await list_student_documents(db_session)
        assert total == 2

    async def test_filters_by_student(self, db_session: AsyncSession) -> None:
        s1, s2 = str(uuid4()), str(uuid4())
        c = str(uuid4())
        await create_student_document(
            db_session, student_external_id=s1, coordinator_external_id=c,
            document_type="rg", description="A",
        )
        await create_student_document(
            db_session, student_external_id=s2, coordinator_external_id=c,
            document_type="cpf", description="B",
        )
        await db_session.commit()

        items, total = await list_student_documents(db_session, student_external_id=s1)
        assert total == 1

    async def test_returns_empty(self, db_session: AsyncSession) -> None:
        items, total = await list_student_documents(db_session)
        assert total == 0


class TestSubmitDocumentToInstitution:
    async def test_submits_document(
        self, db_session: AsyncSession, student_id: str, coordinator_id: str
    ) -> None:
        doc = await create_student_document(
            db_session, student_external_id=student_id,
            coordinator_external_id=coordinator_id,
            document_type="rg", description="RG para envio",
        )
        await db_session.commit()

        result = await submit_document_to_institution(db_session, doc.id)
        assert result is not None
        assert result.submitted_to_institution is True
        assert result.submitted_at is not None

    async def test_returns_none_for_missing(self, db_session: AsyncSession) -> None:
        result = await submit_document_to_institution(db_session, "no-such")
        assert result is None
