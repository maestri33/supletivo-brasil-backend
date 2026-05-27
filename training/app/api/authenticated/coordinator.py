"""Endpoints de coordenador — aprovacao/rejeicao manual da entrevista do trainee.

Gate: papel `coordinator` no JWT. O `external_id` na URL e' o do TRAINEE
(quem esta sendo avaliado); o coordenador e' identificado pelo `external_id`
do proprio JWT (auditoria).
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_coordinator
from app.schemas.trainee import CoordinatorRejectIn, TraineeOut
from app.services import coordinator as coord_svc

router = APIRouter(prefix="/api/v1/coordinator", tags=["coordinator"])


@router.post(
    "/approve-interview/{trainee_external_id}",
    response_model=TraineeOut,
    summary="Aprova entrevista do trainee e promove a promoter",
)
async def approve_interview(
    trainee_external_id: UUID,
    coordinator_external_id: UUID = require_coordinator(),
    session: AsyncSession = Depends(get_session),
):
    trainee = await coord_svc.approve_interview(
        session,
        trainee_external_id=trainee_external_id,
        coordinator_external_id=coordinator_external_id,
    )
    await session.commit()
    return TraineeOut.from_model(trainee)


@router.post(
    "/reject-interview/{trainee_external_id}",
    response_model=TraineeOut,
    summary="Rejeita entrevista do trainee (motivo obrigatorio)",
)
async def reject_interview(
    trainee_external_id: UUID,
    payload: CoordinatorRejectIn,
    coordinator_external_id: UUID = require_coordinator(),
    session: AsyncSession = Depends(get_session),
):
    trainee = await coord_svc.reject_interview(
        session,
        trainee_external_id=trainee_external_id,
        coordinator_external_id=coordinator_external_id,
        reason=payload.reason,
    )
    await session.commit()
    return TraineeOut.from_model(trainee)
