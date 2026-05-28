"""Etapa selfie — assinatura digital + transição para awaiting_release.

Quando a selfie é aceita, o status pula direto para awaiting_release (PRD §5.9)
e o coordenador do hub é notificado (best-effort, async).
"""

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.db import get_session
from app.dependencies import require_education
from app.schemas.selfie import SelfieGetResponse, SelfiePostResponse
from app.services import enrollment as enrollment_svc
from app.services import notifications
from app.services import selfie as selfie_svc

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


@router.get("/selfie", response_model=SelfieGetResponse, summary="Estado da selfie")
async def get_selfie(external_id=require_education()):
    with upstream_errors():
        data = await selfie_svc.get_selfie(str(external_id))
    return SelfieGetResponse(**data)


@router.post(
    "/selfie",
    response_model=SelfiePostResponse,
    summary="Envia selfie e marca matrícula como aguardando liberação",
)
async def post_selfie(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    external_id=require_education(),
):
    content = await file.read()
    with upstream_errors():
        result = await selfie_svc.submit_selfie(
            session,
            str(external_id),
            content,
            file.filename or "selfie",
            file.content_type or "application/octet-stream",
        )
    enrollment = await enrollment_svc.get(session, external_id)
    hub_external_id = (
        str(enrollment.hub_external_id) if enrollment and enrollment.hub_external_id else None
    )
    promoter_external_id = (
        str(enrollment.promoter_external_id)
        if enrollment and enrollment.promoter_external_id
        else None
    )
    await session.commit()

    background_tasks.add_task(
        notifications.notify_status_advanced, str(external_id), result["status"]
    )
    background_tasks.add_task(
        notifications.notify_coordinator_awaiting,
        str(external_id),
        hub_external_id,
        promoter_external_id,
    )
    return SelfiePostResponse(
        status=result["status"],
        verified=result["verified"],
        description=result.get("description"),
    )
