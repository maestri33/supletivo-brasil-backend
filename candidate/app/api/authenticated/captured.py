"""Etapa captured — nome + email; avanca para personal."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.db import get_session
from app.dependencies import require_captured
from app.schemas.profile import CapturedGetResponse, CapturedPostRequest, CapturedPostResponse
from app.services import notifications
from app.services import profile as profile_svc

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


@router.get("/captured", response_model=CapturedGetResponse, summary="Dados do candidato capturado")
async def get_captured(external_id=require_captured()):
    with upstream_errors():
        data = await profile_svc.get_captured(str(external_id))
    return CapturedGetResponse(**data)


@router.post("/captured", response_model=CapturedPostResponse, summary="Salva nome/email")
async def post_captured(
    payload: CapturedPostRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    external_id=require_captured(),
):
    with upstream_errors():
        result = await profile_svc.save_captured(
            session, str(external_id), payload.name, payload.email
        )
    if "errors" in result:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result["errors"]
        )

    await session.commit()

    if result.get("incomplete"):
        return CapturedPostResponse(
            status="incomplete",
            message="Preencha todos os campos para prosseguir",
            name=result.get("name"),
            phone=result.get("phone"),
            email=result.get("email"),
        )

    background_tasks.add_task(
        notifications.notify_status_advanced, str(external_id), result["status"]
    )
    return CapturedPostResponse(
        status=result["status"],
        name=result.get("name"),
        phone=result.get("phone"),
        email=result.get("email"),
    )
