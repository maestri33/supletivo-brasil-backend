"""Etapa personal — dados pessoais; avanca para education."""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.db import get_session
from app.dependencies import require_personal
from app.models import CandidateStatus
from app.schemas.profile import PersonalGetResponse, PersonalPostRequest, PersonalPostResponse
from app.services import notifications
from app.services import profile as profile_svc

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])

_FIELDS = ("gender", "mother_name", "father_name", "marital_status")


@router.get("/personal", response_model=PersonalGetResponse, summary="Dados pessoais")
async def get_personal(external_id=require_personal()):
    with upstream_errors():
        data = await profile_svc.get_profile_fields(str(external_id), _FIELDS)
    return PersonalGetResponse(**data)


@router.post("/personal", response_model=PersonalPostResponse, summary="Salva dados pessoais")
async def post_personal(
    payload: PersonalPostRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    external_id=require_personal(),
):
    with upstream_errors():
        new_status = await profile_svc.save_profile_step(
            session,
            str(external_id),
            current=CandidateStatus.PERSONAL,
            new=CandidateStatus.EDUCATION,
            patch={
                "gender": payload.gender,
                "mother_name": payload.mother_name,
                "father_name": payload.father_name,
                "marital_status": payload.marital_status,
            },
        )
    await session.commit()
    background_tasks.add_task(notifications.notify_status_advanced, str(external_id), new_status)
    return PersonalPostResponse(status=new_status)
