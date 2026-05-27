"""Documentos do aluno — submissao, validacao IA assincrona, listagem."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session_maker
from app.exceptions import (
    DocumentAlreadyExists,
    DocumentNotFound,
    InvalidStatusTransition,
    RequiredDocumentMissing,
)
from app.integrations.ai import AIClient
from app.integrations.documents import DocumentsClient
from app.integrations.profiles import ProfilesClient
from app.models import (
    REQUIRED_DOCUMENT_TYPES,
    DocumentType,
    Student,
    StudentDocument,
    StudentStatus,
    ValidationStatus,
)
from app.services import student_service
from app.utils.logging import get_logger

logger = get_logger("student.documents")
settings = get_settings()


async def submit_document(
    session: AsyncSession,
    *,
    student: Student,
    document_type: DocumentType,
    document_external_id: UUID,
) -> StudentDocument:
    """Aluno cadastra referencia a um documento. 1 doc por tipo (UNIQUE)."""
    existing = await session.scalar(
        select(StudentDocument).where(
            StudentDocument.student_id == student.id,
            StudentDocument.document_type == document_type.value,
        )
    )
    if existing is not None:
        raise DocumentAlreadyExists(
            f"Aluno ja' enviou documento do tipo {document_type.value}"
        )

    doc = StudentDocument(
        student_id=student.id,
        document_type=document_type.value,
        document_external_id=document_external_id,
        validation_status=ValidationStatus.PENDING.value,
    )
    session.add(doc)
    await session.flush()
    await session.refresh(doc)
    return doc


async def list_documents(
    session: AsyncSession, *, student: Student
) -> list[StudentDocument]:
    res = await session.scalars(
        select(StudentDocument)
        .where(StudentDocument.student_id == student.id)
        .order_by(StudentDocument.created_at)
    )
    return list(res.all())


async def submit_for_review(
    session: AsyncSession,
    *,
    student: Student,
) -> list[StudentDocument]:
    """Verifica obrigatorios (consultando profiles p/ gender, §11/§14), transiciona
    para DOCUMENTS_UNDER_REVIEW e devolve a lista de docs a validar em background.

    Nao quebra se profiles cair: nesse caso reservista vira opcional (best-effort).
    """
    docs = await list_documents(session, student=student)
    by_type = {d.document_type: d for d in docs}

    required: set[str] = {t.value for t in REQUIRED_DOCUMENT_TYPES}

    # Regra reservista (PRD §8.3): so' obrigatorio para homens.
    gender = await _safe_get_gender(student.external_id)
    if gender == "male":
        required.add(DocumentType.MILITARY_SERVICE.value)

    missing = required - by_type.keys()
    if missing:
        raise RequiredDocumentMissing(
            "Documentos obrigatorios pendentes: " + ", ".join(sorted(missing))
        )

    student_service.advance(
        student,
        allowed_from=(StudentStatus.AWAITING_DOCUMENTS,),
        to=StudentStatus.DOCUMENTS_UNDER_REVIEW,
    )
    return docs


async def _safe_get_gender(external_id: UUID) -> str | None:
    """Consulta profiles para gender; retorna None em qualquer erro (degrade)."""
    try:
        async with httpx.AsyncClient(
            base_url=settings.profiles_base_url, timeout=settings.http_timeout
        ) as client:
            profile = await ProfilesClient(client).get_one(str(external_id))
        return profile.get("gender")
    except Exception as exc:  # noqa: BLE001 — degrade gracioso
        logger.warning("profiles.get_gender_failed", external_id=str(external_id), error=str(exc))
        return None


async def validate_document_async(student_id: UUID, document_id: UUID) -> None:
    """Background task — descreve a imagem via `ai` e grava validation_status.

    Abre uma sessao propria (BackgroundTasks roda apos commit da requisicao).
    Se a IA cair, doc fica em `pending` e o fluxo nao quebra (§14).
    """
    async with async_session_maker() as session:
        doc = await session.scalar(
            select(StudentDocument).where(StudentDocument.id == document_id)
        )
        if doc is None:
            logger.warning("ai.validate.doc_missing", document_id=str(document_id))
            return

        try:
            async with httpx.AsyncClient(
                base_url=settings.documents_base_url, timeout=settings.http_timeout
            ) as docs_client:
                image_url = DocumentsClient(docs_client).image_url(
                    str(doc.document_external_id), doc.document_type
                )
            async with httpx.AsyncClient(
                base_url=settings.ai_base_url, timeout=settings.http_timeout
            ) as ai_client:
                description = await AIClient(ai_client).vision(image_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ai.validate.failed",
                document_id=str(document_id),
                error=str(exc),
            )
            return

        # Heuristica simples: se a IA produziu uma descricao com o tipo esperado
        # mencionado, aprova. Reprovacao explicita exige logica futura no `ai`.
        decision = _heuristic_decision(doc.document_type, description)
        doc.validation_status = decision.value
        doc.validation_result = {"description": description, "decision": decision.value}
        doc.validated_at = datetime.now(UTC)
        await session.commit()

        # Se for a ultima pendente do aluno e todas aprovadas, libera prova.
        await _maybe_release_exam(session, student_id)


def _heuristic_decision(document_type: str, description: str) -> ValidationStatus:
    """Heuristica naive: descricao nao vazia => approved; vazia => pending.

    Nao decide rejected sozinha — exige sinal explicito do `ai` (futuro).
    """
    if not description or not description.strip():
        return ValidationStatus.PENDING
    return ValidationStatus.APPROVED


async def _maybe_release_exam(session: AsyncSession, student_id: UUID) -> None:
    """Se todos os obrigatorios estao aprovados, transita p/ EXAM_RELEASED."""
    student = await session.scalar(select(Student).where(Student.id == student_id))
    if student is None or student.status != StudentStatus.DOCUMENTS_UNDER_REVIEW:
        return

    required = {t.value for t in REQUIRED_DOCUMENT_TYPES}
    gender = await _safe_get_gender(student.external_id)
    if gender == "male":
        required.add(DocumentType.MILITARY_SERVICE.value)

    docs = await session.scalars(
        select(StudentDocument).where(StudentDocument.student_id == student_id)
    )
    docs_list = list(docs.all())

    required_docs = [d for d in docs_list if d.document_type in required]
    if len(required_docs) < len(required):
        return  # ainda faltam docs cadastrados
    if not all(d.validation_status == ValidationStatus.APPROVED.value for d in required_docs):
        return  # ainda ha' algum pendente/rejeitado

    try:
        student_service.advance(
            student,
            allowed_from=(StudentStatus.DOCUMENTS_UNDER_REVIEW,),
            to=StudentStatus.EXAM_RELEASED,
        )
        await session.commit()
        logger.info("student.exam_released", student_id=str(student_id))
    except InvalidStatusTransition:
        pass


async def list_rejected(session: AsyncSession, *, student: Student) -> list[StudentDocument]:
    """Helper de pendencias — docs com validation_status=rejected."""
    res = await session.scalars(
        select(StudentDocument).where(
            StudentDocument.student_id == student.id,
            StudentDocument.validation_status == ValidationStatus.REJECTED.value,
        )
    )
    return list(res.all())


async def get_document(
    session: AsyncSession, *, student: Student, document_id: UUID
) -> StudentDocument:
    doc = await session.scalar(
        select(StudentDocument).where(
            StudentDocument.id == document_id,
            StudentDocument.student_id == student.id,
        )
    )
    if doc is None:
        raise DocumentNotFound(f"Documento {document_id} nao encontrado para este aluno")
    return doc
