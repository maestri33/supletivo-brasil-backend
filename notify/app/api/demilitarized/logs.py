"""Endpoints de logs do sistema (SQLAlchemy 2)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.log import LogRead
from app.services import log_service, metrics_service

router = APIRouter()


@router.get("", response_model=list[LogRead], summary="Listar logs")
async def list_logs(
    message_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[LogRead]:
    if message_id is not None:
        records = await log_service.list_logs_by_message(
            session,
            message_id,
            limit=limit,
            offset=offset,
        )
    else:
        records = await log_service.list_logs(session, limit=limit, offset=offset)
    return [LogRead.model_validate(r, from_attributes=True) for r in records]


@router.get(
    "/by-external-id/{external_id}",
    response_model=list[LogRead],
    summary="Timeline de logs por usuario (external_id)",
)
async def list_logs_by_external_id(
    external_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[LogRead]:
    """Lista todos os logs associados a um external_id.

    Inclui logs por `external_id` direto e logs ligados via message → contact.
    Ordenacao por created_at desc (mais recente primeiro).
    """
    records = await log_service.list_logs_by_external_id(
        session,
        external_id,
        limit=limit,
        offset=offset,
    )
    return [LogRead.model_validate(r, from_attributes=True) for r in records]


@router.get("/metrics", summary="Metricas agregadas (mensagens + erros + templates)")
async def metrics(
    window_hours: int = Query(default=24, ge=1, le=720),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Snapshot completo de metricas. Usado por dashboards e o /status root.

    `window_hours` controla o tamanho da janela das agregadas temporais
    (mensagens recentes, top erros). Min 1h, max 30 dias.
    """
    return {
        "window_hours": window_hours,
        "messages": await metrics_service.messages_summary(session, window_hours),
        "recent_errors": await metrics_service.top_errors(session, window_hours, limit=10),
    }
