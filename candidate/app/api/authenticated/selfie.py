"""Etapa selfie — selfie real + conclusao (promove a training); status completed."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.db import get_session
from app.dependencies import require_selfie
from app.schemas.selfie import SelfieGetResponse, SelfiePostResponse
from app.services import candidate as candidate_svc
from app.services import notifications
from app.services import selfie as selfie_svc

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


@router.get("/selfie", response_model=SelfieGetResponse, summary="Estado da selfie")
async def get_selfie(external_id=require_selfie()):
    with upstream_errors():
        data = await selfie_svc.get_selfie(str(external_id))
    return SelfieGetResponse(**data)


@router.post(
    "/selfie", response_model=SelfiePostResponse, summary="Envia selfie e conclui cadastro"
)
async def post_selfie(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    external_id=require_selfie(),
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
    candidate = await candidate_svc.get(session, str(external_id))
    hub_external_id = (
        str(candidate.hub_external_id) if candidate and candidate.hub_external_id else None
    )
    await session.commit()

    background_tasks.add_task(
        notifications.notify_status_advanced, str(external_id), result["status"]
    )
    background_tasks.add_task(notifications.notify_hub_completed, str(external_id), hub_external_id)
    return SelfiePostResponse(
        status=result["status"],
        verified=result["verified"],
        description=result.get("description"),
    )
