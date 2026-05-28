"""Submissoes autenticadas — trainee envia resposta e lista as proprias.

Endpoints:
- POST   /api/v1/submissions               → cria submissao e dispara grading em BG
- GET    /api/v1/submissions/me            → lista submissoes do JWT atual
- GET    /api/v1/submissions/{id}          → busca submissao (se for do JWT atual)
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_trainee
from app.exceptions import Conflict, NotFound
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionListResponse,
    SubmissionOut,
)
from app.services import material as material_svc
from app.services import submission as submission_svc
from app.services import trainee as trainee_svc
from app.services.grading import run_grading

router = APIRouter(prefix="/api/v1", tags=["authenticated"])


@router.post(
    "/submissions",
    response_model=SubmissionOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Envia resposta para uma materia (dispara correcao IA em background)",
)
async def submit_answer(
    payload: SubmissionCreate,
    background: BackgroundTasks,
    external_id: UUID = require_trainee(),
    session: AsyncSession = Depends(get_session),
):
    # 1. Materia precisa existir
    await material_svc.get_or_404(session, payload.material_id)

    # 2. Bloqueia se ja' tem submissao pendente p/ esta materia (evita gastar IA em duplicado)
    if await submission_svc.has_pending(session, external_id, payload.material_id):
        raise Conflict("Voce ja' tem uma submissao em correcao para esta materia")

    # 3. Garante o trainee na primeira submissao (idempotente)
    await trainee_svc.get_or_create(session, external_id)

    # 4. Cria a submissao em status pending
    sub = await submission_svc.create(
        session,
        external_id=external_id,
        material_id=payload.material_id,
        answer=payload.answer,
    )
    await session.commit()

    # 5. Background grading — roda apos a resposta HTTP (CONVENTION §13)
    background.add_task(run_grading, sub.id)
    return SubmissionOut.from_model(sub)


@router.get(
    "/submissions/me",
    response_model=SubmissionListResponse,
    summary="Lista submissoes do trainee autenticado",
)
async def list_my_submissions(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    external_id: UUID = require_trainee(),
    session: AsyncSession = Depends(get_session),
):
    rows = await submission_svc.list_by_user(session, external_id, limit=limit, offset=offset)
    return SubmissionListResponse(
        total=len(rows), submissions=[SubmissionOut.from_model(r) for r in rows]
    )


@router.get(
    "/submissions/{submission_id}",
    response_model=SubmissionOut,
    summary="Busca uma submissao do trainee autenticado",
)
async def get_my_submission(
    submission_id: str,
    external_id: UUID = require_trainee(),
    session: AsyncSession = Depends(get_session),
):
    sub = await submission_svc.get_or_404(session, submission_id)
    if sub.external_id != str(external_id):
        # Trate como 404 para nao vazar existencia do recurso de outro user
        raise NotFound("Submissao nao encontrada")
    return SubmissionOut.from_model(sub)
