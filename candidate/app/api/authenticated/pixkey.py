"""Etapa pixkey — cadastra/valida a chave PIX no asaas; avanca para selfie."""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.db import get_session
from app.dependencies import require_pixkey
from app.schemas.pixkey import PixKeyGetResponse, PixKeyPostRequest, PixKeyPostResponse
from app.services import notifications
from app.services import pixkey as pixkey_svc

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


@router.get("/pixkey", response_model=PixKeyGetResponse, summary="Chave PIX cadastrada")
async def get_pixkey(external_id=require_pixkey()):
    with upstream_errors():
        data = await pixkey_svc.get_pixkey(str(external_id))
    return PixKeyGetResponse(**data) if data else PixKeyGetResponse()


@router.post("/pixkey", response_model=PixKeyPostResponse, summary="Valida e cadastra chave PIX")
async def post_pixkey(
    payload: PixKeyPostRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    external_id=require_pixkey(),
):
    with upstream_errors():
        result = await pixkey_svc.save_pixkey(
            session, str(external_id), payload.key, payload.key_type
        )
    await session.commit()
    background_tasks.add_task(
        notifications.notify_status_advanced, str(external_id), result["status"]
    )
    return PixKeyPostResponse(
        status=result["status"],
        holder_name=result.get("holder_name"),
        bank_name=result.get("bank_name"),
    )
