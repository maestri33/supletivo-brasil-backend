"""Endpoint authenticated/completed — lead com pagamento confirmado."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_completed
from app.models import Checkout, Lead
from app.schemas import APIModel

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


class CompletedGetResponse(APIModel):
    status: str
    message: str = "Parabens! Cadastro concluido com sucesso"
    receipt_url: str | None = None


@router.get(
    "/completed",
    response_model=CompletedGetResponse,
    summary="Verifica status completed do lead",
)
async def get_completed(
    external_id: UUID = require_completed(),
    session: AsyncSession = Depends(get_session),
):
    lead = await session.scalar(select(Lead).where(Lead.external_id == external_id))
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead nao encontrado")

    checkout = await session.scalar(select(Checkout).where(Checkout.external_id == external_id))
    if not checkout:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Pagamento nao processado")

    return CompletedGetResponse(
        status=lead.status.value,
        receipt_url=checkout.receipt_url,
    )
