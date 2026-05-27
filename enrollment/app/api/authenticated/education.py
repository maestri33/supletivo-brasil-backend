"""Etapa education — dados educacionais; avança documents → education."""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_documents
from app.schemas.education import (
    EducationGetResponse,
    EducationPostRequest,
    EducationPostResponse,
)
from app.services import education as education_svc
from app.services import notifications

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


@router.get("/education", response_model=EducationGetResponse, summary="Dados educacionais")
async def get_education(
    session: AsyncSession = Depends(get_session),
    external_id=require_documents(),
):
    data = await education_svc.get_education(session, str(external_id))
    return EducationGetResponse(**data) if data else EducationGetResponse()


@router.post("/education", response_model=EducationPostResponse, summary="Envia dados educacionais")
async def post_education(
    payload: EducationPostRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    external_id=require_documents(),
):
    new_status = await education_svc.save_education(session, str(external_id), payload)
    await session.commit()
    background_tasks.add_task(notifications.notify_status_advanced, str(external_id), new_status)
    return EducationPostResponse(status=new_status)
