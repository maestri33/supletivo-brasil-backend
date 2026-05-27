"""Etapa birth — dados de nascimento; avanca para address."""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.db import get_session
from app.dependencies import require_birth
from app.models import CandidateStatus
from app.schemas.profile import BirthGetResponse, BirthPostRequest, BirthPostResponse
from app.services import notifications
from app.services import profile as profile_svc

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])

_FIELDS = ("date_of_birth", "birthplace", "nationality")


@router.get("/birth", response_model=BirthGetResponse, summary="Dados de nascimento")
async def get_birth(external_id=require_birth()):
    with upstream_errors():
        data = await profile_svc.get_profile_fields(str(external_id), _FIELDS)
    return BirthGetResponse(**data)


@router.post("/birth", response_model=BirthPostResponse, summary="Salva dados de nascimento")
async def post_birth(
    payload: BirthPostRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    external_id=require_birth(),
):
    with upstream_errors():
        new_status = await profile_svc.save_profile_step(
            session,
            str(external_id),
            current=CandidateStatus.BIRTH,
            new=CandidateStatus.ADDRESS,
            patch={
                "date_of_birth": payload.date_of_birth.isoformat(),
                "birthplace": payload.birthplace,
                "nationality": payload.nationality,
            },
        )
    await session.commit()
    background_tasks.add_task(notifications.notify_status_advanced, str(external_id), new_status)
    return BirthPostResponse(status=new_status)
