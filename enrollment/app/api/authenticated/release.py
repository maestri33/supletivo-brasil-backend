"""Liberação manual da matrícula pelo coordenador → conclusão.

Gate: JWT com role `coordinator` (CONVENTION §8 — roles vêm do JWT do
serviço `roles`, não do DB local). Promove o matriculando enrollment →
student e marca a matrícula como completed.
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.db import get_session
from app.dependencies import get_current_coordinator
from app.exceptions import Conflict
from app.models import EnrollmentStatus
from app.schemas.release import ReleasePostResponse, ReleasePostRequest
from app.services import enrollment as enrollment_svc
from app.services import notifications
from app.services import release as release_svc

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


@router.post(
    "/enrollments/{external_id}/release",
    response_model=ReleasePostResponse,
    summary="Coordenador libera a matrícula e promove o aluno",
)
async def post_release(
    payload: ReleasePostRequest,
    background_tasks: BackgroundTasks,
    external_id: UUID = Path(..., description="UUID do matriculando"),
    session: AsyncSession = Depends(get_session),
    coordinator_external_id: UUID = Depends(get_current_coordinator),
):
    # Gate de status (não dá pra reusar require_awaiting_release porque ele
    # depende de JWT com role 'enrollment' — aqui o JWT é do coordenador).
    enrollment = await enrollment_svc.get(session, external_id)
    if enrollment is None:
        raise Conflict("Matrícula não encontrada", code="ENROLLMENT_NOT_FOUND")
    if enrollment.status != EnrollmentStatus.AWAITING_RELEASE.value:
        raise Conflict(
            f"Matrícula em '{enrollment.status}' — requer 'awaiting_release'",
            code="INVALID_STATUS",
        )

    with upstream_errors():
        new_status = await release_svc.release(
            session, str(external_id), payload, str(coordinator_external_id)
        )
    await session.commit()
    background_tasks.add_task(notifications.notify_status_advanced, str(external_id), new_status)
    return ReleasePostResponse(status=new_status)
