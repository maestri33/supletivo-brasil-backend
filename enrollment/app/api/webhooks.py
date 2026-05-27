"""Recebe webhooks do lead na bifurcação lead.completed."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.exceptions import Conflict, NotFound
from app.models import EnrollmentEvent
from app.schemas import EnrollmentEventRead, WebhookPayload
from app.services import enrollment as enrollment_svc

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["webhooks"])


@router.post(
    "/webhook/new/{external_id}",
    status_code=202,
    summary="Receber bifurcação do lead (event=lead.completed)",
)
async def receive(
    external_id: UUID,
    payload: dict = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Recebe POST do lead quando Lead.status → COMPLETED.

    Persiste o evento. A lógica de matrícula real consome esses eventos depois.

    Idempotente: se já existe um evento para o mesmo (external_id, event), não
    duplica — retorna o id existente com already_exists=True. O caller (lead)
    pode reenviar o webhook sem gerar linhas duplicadas no log auditivo.
    """
    body = WebhookPayload(**payload) if payload else WebhookPayload()

    # structlog: o primeiro arg posicional vira o campo "event" do log.
    # Passar event=... como kwarg conflita ("got multiple values for argument 'event'").
    # Usamos event_type=... aqui para evitar colisao.
    existing = await session.scalar(
        select(EnrollmentEvent)
        .where(
            EnrollmentEvent.external_id == external_id,
            EnrollmentEvent.event == body.event,
        )
        .limit(1)
    )
    if existing is not None:
        # Evento já logado: garante o agregado mesmo para eventos anteriores a
        # este milestone (idempotente). O usuário já existe → FK satisfeita.
        enrollment, _ = await enrollment_svc.get_or_create(
            session, external_id, body.promoter_external_id
        )
        await session.commit()
        logger.info(
            "enrollment_event_already_exists",
            external_id=str(external_id),
            event_type=body.event,
            id=existing.id,
            enrollment_id=str(enrollment.id),
        )
        return {
            "ok": True,
            "already_exists": True,
            "id": existing.id,
            "enrollment_id": str(enrollment.id),
            "status": enrollment.status,
            "event": body.event,
        }

    event = EnrollmentEvent(
        external_id=external_id,
        event=body.event,
        promoter_external_id=body.promoter_external_id,
        payload=payload or {},
    )
    session.add(event)
    try:
        # Evento auditivo + agregado de matrícula na mesma transação.
        enrollment, _ = await enrollment_svc.get_or_create(
            session, external_id, body.promoter_external_id
        )
        await session.commit()
    except IntegrityError:
        # FK cross-schema: external_id precisa existir em auth.users.
        await session.rollback()
        logger.warning(
            "enrollment_event_unknown_external_id",
            external_id=str(external_id),
            event_type=body.event,
        )
        raise Conflict(
            detail="external_id não encontrado em auth.users",
            code="UNKNOWN_EXTERNAL_ID",
        ) from None
    await session.refresh(event)

    logger.info(
        "enrollment_event_received",
        external_id=str(external_id),
        event_type=body.event,
        promoter=str(body.promoter_external_id) if body.promoter_external_id else None,
        id=event.id,
        enrollment_id=str(enrollment.id),
    )
    return {
        "ok": True,
        "id": event.id,
        "enrollment_id": str(enrollment.id),
        "status": enrollment.status,
        "event": body.event,
    }


@router.get(
    "/events",
    response_model=list[EnrollmentEventRead],
    summary="Listar eventos (audit)",
)
async def list_events(
    external_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[EnrollmentEventRead]:
    stmt = select(EnrollmentEvent).order_by(EnrollmentEvent.received_at.desc())
    if external_id:
        stmt = stmt.where(EnrollmentEvent.external_id == external_id)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.scalars(stmt)
    return [EnrollmentEventRead.model_validate(e) for e in result.all()]


@router.get(
    "/events/{event_id}",
    response_model=EnrollmentEventRead,
    summary="Obter evento por id",
)
async def get_event(
    event_id: int,
    session: AsyncSession = Depends(get_session),
) -> EnrollmentEventRead:
    event = await session.get(EnrollmentEvent, event_id)
    if not event:
        raise NotFound("Evento não encontrado")
    return EnrollmentEventRead.model_validate(event)
