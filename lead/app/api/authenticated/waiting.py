"""Endpoint authenticated/waiting — lead aguarda checkout ser gerado."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_waiting
from app.models import Lead, LeadStatus
from app.schemas import APIModel

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


class WaitingGetResponse(APIModel):
    status: str
    message: str = "Aguarde, estamos processando seus dados"
    error_code: str | None = None


@router.get(
    "/waiting",
    response_model=WaitingGetResponse,
    summary="Verifica status waiting do lead",
)
async def get_waiting(
    external_id: UUID = require_waiting(),
    session: AsyncSession = Depends(get_session),
):
    lead = await session.scalar(select(Lead).where(Lead.external_id == external_id))
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead nao encontrado")
    if lead.status == LeadStatus.FAILED:
        return WaitingGetResponse(
            status=lead.status.value,
            message="Falha ao gerar checkout. Tente novamente.",
            error_code=lead.failed_reason or "checkout_create_failed",
        )
    return WaitingGetResponse(status=lead.status.value)
