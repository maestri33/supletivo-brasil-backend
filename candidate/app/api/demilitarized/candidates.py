"""Rotas desmilitarizadas (consumidas so' dentro da plataforma, sem auth — §5).

Listagem/filtragem de candidatos por hub/status e busca por external_id, para
outros servicos (hub, coordinator, etc.) inspecionarem o funil.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.candidate import CandidateListResponse, CandidateOut
from app.services import candidate as candidate_svc

router = APIRouter(prefix="/api/v1/demilitarized", tags=["demilitarized"])


@router.get("/candidates", response_model=CandidateListResponse, summary="Lista/filtra candidatos")
async def list_candidates(
    hub_external_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    rows = await candidate_svc.list_candidates(
        session,
        hub_external_id=str(hub_external_id) if hub_external_id else None,
        status=status,
        limit=limit,
        offset=offset,
    )
    return CandidateListResponse(
        total=len(rows),
        candidates=[CandidateOut.model_validate(r, from_attributes=True) for r in rows],
    )


@router.get(
    "/candidates/{external_id}",
    response_model=CandidateOut,
    summary="Busca candidato por external_id",
)
async def get_candidate(external_id: UUID, session: AsyncSession = Depends(get_session)):
    candidate = await candidate_svc.get(session, external_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato nao encontrado")
    return CandidateOut.model_validate(candidate, from_attributes=True)
