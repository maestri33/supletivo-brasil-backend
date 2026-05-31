"""Progresso do trainee em uma materia (visao do usuario autenticado).

Retorna o status do trainee NESSA materia: ultima submissao, nota,
justificativa, tentativas. Status `not_started` quando nunca submeteu.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_trainee
from app.schemas.submission import MaterialProgressOut
from app.services import material as material_svc
from app.services import submission as submission_svc

router = APIRouter(prefix="/api/v1", tags=["authenticated"])


@router.get(
    "/materials/{material_id}/progress",
    response_model=MaterialProgressOut,
    summary="Progresso do trainee nesta materia",
)
async def material_progress(
    material_id: str,
    external_id: UUID = require_trainee(),
    session: AsyncSession = Depends(get_session),
):
    await material_svc.get_or_404(session, material_id)
    last = await submission_svc.get_last_for_material(session, external_id, material_id)
    attempts = await submission_svc.count_attempts(session, external_id, material_id)

    if last is None:
        return MaterialProgressOut(
            material_id=str(material_id),
            status="not_started",
            attempts=0,
        )
    return MaterialProgressOut(
        material_id=str(material_id),
        status=last.status,
        grade=last.grade,
        justification=last.justification,
        attempts=attempts,
        last_submission_id=str(last.id),
        last_submission_at=last.created_at,
    )
