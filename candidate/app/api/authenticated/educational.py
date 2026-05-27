"""Etapa education — dados educacionais; avanca para birth."""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.db import get_session
from app.dependencies import require_education
from app.models import CandidateStatus
from app.schemas.profile import (
    EducationalGetResponse,
    EducationalPostRequest,
    EducationalPostResponse,
)
from app.services import notifications
from app.services import profile as profile_svc

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])

_FIELDS = ("education_level", "institution", "course", "completion_year")


@router.get("/educational", response_model=EducationalGetResponse, summary="Dados educacionais")
async def get_educational(external_id=require_education()):
    with upstream_errors():
        data = await profile_svc.get_profile_fields(str(external_id), _FIELDS)
    return EducationalGetResponse(**data)


@router.post(
    "/educational", response_model=EducationalPostResponse, summary="Salva dados educacionais"
)
async def post_educational(
    payload: EducationalPostRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    external_id=require_education(),
):
    with upstream_errors():
        new_status = await profile_svc.save_profile_step(
            session,
            str(external_id),
            current=CandidateStatus.EDUCATION,
            new=CandidateStatus.BIRTH,
            patch={
                "education_level": payload.education_level,
                "institution": payload.institution,
                "course": payload.course,
                "completion_year": payload.completion_year,
            },
        )
    await session.commit()
    background_tasks.add_task(notifications.notify_status_advanced, str(external_id), new_status)
    return EducationalPostResponse(status=new_status)
