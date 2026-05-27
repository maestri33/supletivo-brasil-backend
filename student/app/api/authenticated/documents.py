"""Documentos do aluno — submissao, listagem, submit-for-review (role student)."""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_student_with_status
from app.models import Student, StudentStatus
from app.schemas import (
    DocumentSubmitRequest,
    StudentDocumentList,
    StudentDocumentRead,
)
from app.services import document_service, notifications

router = APIRouter(prefix="/api/v1/authenticated/students", tags=["documents"])


@router.get("/me/documents", response_model=StudentDocumentList)
async def list_my_documents(
    student: Student = require_student_with_status(
        StudentStatus.AWAITING_DOCUMENTS,
        StudentStatus.DOCUMENTS_UNDER_REVIEW,
        StudentStatus.EXAM_RELEASED,
        StudentStatus.EXAM_SCHEDULED,
        StudentStatus.EXAM_FAILED,
        StudentStatus.AWAITING_DOCUMENTATION_DISPATCH,
        StudentStatus.PENDING,
        StudentStatus.AWAITING_DIPLOMA_ISSUANCE,
        StudentStatus.AWAITING_PICKUP,
        StudentStatus.VETERAN,
    ),
    session: AsyncSession = Depends(get_session),
) -> StudentDocumentList:
    docs = await document_service.list_documents(session, student=student)
    return StudentDocumentList(
        items=[StudentDocumentRead.model_validate(d) for d in docs],
        total=len(docs),
    )


@router.post(
    "/me/documents",
    response_model=StudentDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_my_document(
    body: DocumentSubmitRequest,
    student: Student = require_student_with_status(
        StudentStatus.AWAITING_DOCUMENTS,
        StudentStatus.DOCUMENTS_UNDER_REVIEW,
    ),
    session: AsyncSession = Depends(get_session),
) -> StudentDocumentRead:
    doc = await document_service.submit_document(
        session,
        student=student,
        document_type=body.document_type,
        document_external_id=body.document_external_id,
    )
    await session.commit()
    return StudentDocumentRead.model_validate(doc)


@router.post("/me/documents/submit-for-review", response_model=StudentDocumentList)
async def submit_for_review(
    background_tasks: BackgroundTasks,
    student: Student = require_student_with_status(StudentStatus.AWAITING_DOCUMENTS),
    session: AsyncSession = Depends(get_session),
) -> StudentDocumentList:
    docs = await document_service.submit_for_review(session, student=student)
    await session.commit()
    # validacao IA assincrona — uma task por documento (idempotente por id)
    for doc in docs:
        background_tasks.add_task(
            document_service.validate_document_async, student.id, doc.id
        )
    background_tasks.add_task(
        notifications.notify_status_changed,
        str(student.external_id),
        student.status,
    )
    # recarrega depois do commit p/ pegar timestamps atualizados
    refreshed = await document_service.list_documents(session, student=student)
    return StudentDocumentList(
        items=[StudentDocumentRead.model_validate(d) for d in refreshed],
        total=len(refreshed),
    )
