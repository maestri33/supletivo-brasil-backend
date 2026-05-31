"""Etapa profile — dados pessoais; avança started → profile."""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.db import get_session
from app.dependencies import require_started
from app.schemas.profile import ProfileGetResponse, ProfilePostRequest, ProfilePostResponse
from app.services import notifications
from app.services import profile as profile_svc

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


@router.get("/profile", response_model=ProfileGetResponse, summary="Dados pessoais atuais")
async def get_profile(external_id=require_started()):
    with upstream_errors():
        data = await profile_svc.get_profile(str(external_id))
    return ProfileGetResponse(**data)


@router.post("/profile", response_model=ProfilePostResponse, summary="Envia dados pessoais")
async def post_profile(
    payload: ProfilePostRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    external_id=require_started(),
):
    with upstream_errors():
        new_status = await profile_svc.save_profile(session, str(external_id), payload)
    await session.commit()
    background_tasks.add_task(notifications.notify_status_advanced, str(external_id), new_status)
    return ProfilePostResponse(status=new_status)
