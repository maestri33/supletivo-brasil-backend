"""Leitura do agregado de matrícula (audit — desmilitarizado)."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.exceptions import NotFound
from app.schemas import EnrollmentRead
from app.services import enrollment as enrollment_svc

router = APIRouter(prefix="/api/v1", tags=["enrollments"])


@router.get(
    "/enrollments/{external_id}",
    response_model=EnrollmentRead,
    summary="Obter a matrícula de um usuário",
)
async def get_enrollment(
    external_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> EnrollmentRead:
    enrollment = await enrollment_svc.get(session, external_id)
    if enrollment is None:
        raise NotFound("Matrícula não encontrada")
    return EnrollmentRead.model_validate(enrollment)
