"""Endpoints autenticados do aluno — promocao (coordenador) e consulta (aluno)."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_role
from app.schemas import PromoteRequest, StudentRead
from app.services import student_service

router = APIRouter(prefix="/api/v1/authenticated/students", tags=["students"])


@router.post("", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
async def promote_student(
    body: PromoteRequest,
    _coordinator: UUID = require_role("coordinator"),
    session: AsyncSession = Depends(get_session),
) -> StudentRead:
    """Coordenador promove um matriculado a aluno (enrollment->student)."""
    student = await student_service.promote(
        session, external_id=body.external_id, study_platform=body.study_platform
    )
    await session.commit()
    return StudentRead.model_validate(student)


@router.get("/me", response_model=StudentRead)
async def get_my_data(
    external_id: UUID = require_role("student"),
    session: AsyncSession = Depends(get_session),
) -> StudentRead:
    """Aluno consulta os proprios dados a qualquer momento."""
    student = await student_service.get_by_external_id(session, external_id)
    return StudentRead.model_validate(student)
