"""CRUD de leads — endpoints internos entre serviços (demilitarized)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Lead, LeadStatus
from app.schemas import APIModel

router = APIRouter(prefix="/api/v1/demilitarized", tags=["demilitarized"])


class LeadOut(APIModel):
    id: int
    external_id: UUID
    status: str
    promoter_external_id: UUID | None = None
    created_at: str | None = None
    updated_at: str | None = None


class LeadPatch(APIModel):
    status: LeadStatus | None = None
    promoter_external_id: UUID | None = None


def _to_out(lead: Lead) -> LeadOut:
    return LeadOut(
        id=lead.id,
        external_id=lead.external_id,
        status=lead.status.value if isinstance(lead.status, LeadStatus) else str(lead.status),
        promoter_external_id=lead.promoter_external_id,
        created_at=lead.created_at.isoformat() if lead.created_at else None,
        updated_at=lead.updated_at.isoformat() if lead.updated_at else None,
    )


@router.get("/leads", response_model=list[LeadOut], summary="Lista todos os leads")
async def list_leads(session: AsyncSession = Depends(get_session)):
    result = await session.scalars(select(Lead).order_by(Lead.created_at.desc(), Lead.external_id.desc()))
    return [_to_out(lead) for lead in result.all()]


@router.get("/leads/{external_id}", response_model=LeadOut, summary="Busca lead por external_id")
async def get_lead(external_id: UUID, session: AsyncSession = Depends(get_session)):
    lead = await session.scalar(select(Lead).where(Lead.external_id == external_id))
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead nao encontrado")
    return _to_out(lead)


@router.patch(
    "/leads/{external_id}",
    response_model=LeadOut,
    summary="Atualiza lead (status ou promoter)",
)
async def patch_lead(
    external_id: UUID,
    payload: LeadPatch,
    session: AsyncSession = Depends(get_session),
):
    lead = await session.scalar(select(Lead).where(Lead.external_id == external_id))
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead nao encontrado")

    if payload.status is not None:
        lead.status = payload.status
    if payload.promoter_external_id is not None:
        lead.promoter_external_id = payload.promoter_external_id

    await session.commit()
    await session.refresh(lead)
    return _to_out(lead)


@router.delete(
    "/leads/{external_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove lead",
)
async def delete_lead(external_id: UUID, session: AsyncSession = Depends(get_session)):
    lead = await session.scalar(select(Lead).where(Lead.external_id == external_id))
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead nao encontrado")
    await session.delete(lead)
    await session.commit()
