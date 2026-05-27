"""Rotas desmilitarizadas (uso interno da plataforma, sem auth — §5).

- POST /promoters         : o `coordinator` cria o promoter apos aprovar o
                            candidato na entrevista (promove papel + cria registro).
- GET  /promoters         : lista/filtra (hub/coordinator inspecionam).
- GET  /promoters/{id}    : busca por external_id.
- GET  /validate-ref/{id} : o `lead` valida o `ref` da captacao.
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.config import get_settings
from app.db import get_session
from app.schemas.promoter import (
    PromoterCreate,
    PromoterListResponse,
    PromoterOut,
    RefValidation,
)
from app.services import notifications
from app.services import promoter as promoter_svc

settings = get_settings()

router = APIRouter(prefix="/api/v1/demilitarized", tags=["demilitarized"])


def _to_out(promoter) -> PromoterOut:
    out = PromoterOut.model_validate(promoter, from_attributes=True)
    out.ref_url = notifications.ref_url(promoter.external_id)
    return out


@router.post(
    "/promoters",
    response_model=PromoterOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cria promoter (chamado pelo coordinator)",
)
async def create_promoter(
    payload: PromoterCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    hub_external_id = (
        str(payload.hub_external_id) if payload.hub_external_id else settings.hub_default
    )
    with upstream_errors():
        promoter, created = await promoter_svc.create_promoter(
            session, payload.external_id, hub_external_id
        )
    await session.commit()
    await session.refresh(promoter)

    if created:
        background_tasks.add_task(
            notifications.notify_promoter_created, promoter.external_id, hub_external_id
        )

    return _to_out(promoter)


@router.get("/promoters", response_model=PromoterListResponse, summary="Lista/filtra promoters")
async def list_promoters(
    hub_external_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    rows = await promoter_svc.list_promoters(
        session,
        hub_external_id=str(hub_external_id) if hub_external_id else None,
        status=status,
        limit=limit,
        offset=offset,
    )
    return PromoterListResponse(total=len(rows), promoters=[_to_out(r) for r in rows])


@router.get(
    "/promoters/{external_id}",
    response_model=PromoterOut,
    summary="Busca promoter por external_id",
)
async def get_promoter(external_id: UUID, session: AsyncSession = Depends(get_session)):
    promoter = await promoter_svc.get(session, external_id)
    if not promoter:
        raise HTTPException(status_code=404, detail="Promotor nao encontrado")
    return _to_out(promoter)


@router.get(
    "/validate-ref/{ref}",
    response_model=RefValidation,
    summary="Valida o ref da captacao (consumido pelo lead)",
)
async def validate_ref(ref: UUID, session: AsyncSession = Depends(get_session)):
    promoter = await promoter_svc.validate_ref(session, ref)
    if promoter is None:
        return RefValidation(valid=False)
    return RefValidation(
        valid=True,
        external_id=promoter.external_id,
        hub_external_id=promoter.hub_external_id,
        status=promoter.status,
    )
