"""Pendencias do aluno (PRD §5.6) — escopo minimo: status + docs reprovados."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_student_with_status
from app.models import Student, StudentStatus
from app.schemas import PendingItemsResponse, StudentDocumentRead
from app.services import document_service

router = APIRouter(prefix="/api/v1/authenticated/students", tags=["pending"])


@router.get("/me/pending-items", response_model=PendingItemsResponse)
async def get_my_pending(
    student: Student = require_student_with_status(
        *list(StudentStatus),
    ),
    session: AsyncSession = Depends(get_session),
) -> PendingItemsResponse:
    rejected = await document_service.list_rejected(session, student=student)
    return PendingItemsResponse(
        status=student.status,
        rejected_documents=[StudentDocumentRead.model_validate(d) for d in rejected],
    )
