"""Webhook interno (desmilitarizado) — recebe status de payout do asaas (§5).

O asaas faz `POST {internal_url_payout|internal_url_scheduling}` a cada transição
de status com `{"payment_id", "kind", "external_id", "status"}`. Como em payouts
de QR Code o `external_id` vem nulo, a correlação é por `payment_id` (o id
idempotente que o fees enviou). Endpoint consumido só por outro app da
plataforma — sem auth, conforme §5.
"""

from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import FeeStatus
from app.notify.handlers import (
    notify_coordinator_payment_failed,
    notify_student_access_released,
    notify_student_fully_paid,
)
from app.schemas import AsaasPayoutWebhook
from app.services import fee_service

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/webhook", tags=["webhooks"])


@router.post("/asaas-payout", status_code=status.HTTP_202_ACCEPTED)
async def asaas_payout_callback(
    background_tasks: BackgroundTasks,
    raw: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Aplica o status de um payout a uma parcela de taxa.

    Aceita o ping de onboarding do asaas (`event=ASAAS_APP_ONBOARDING`) sem
    efeito colateral. Idempotente: re-entregar o mesmo status não re-notifica.
    """
    if raw.get("event") == "ASAAS_APP_ONBOARDING":
        logger.info("asaas_webhook_onboarding_ack", target=raw.get("target"))
        return {"ok": True, "onboarding": True}

    try:
        payload = AsaasPayoutWebhook.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 — webhook inválido não deve dar 500
        logger.warning("asaas_webhook_invalid_payload", error=str(exc)[:200])
        return {"ok": True, "invalid_payload": True}

    outcome = await fee_service.apply_payout_webhook(
        session, payment_id=payload.payment_id, status=payload.status
    )
    if outcome is None:
        logger.info("asaas_webhook_unknown_payment", payment_id=payload.payment_id)
        return {"ok": True, "ignored": True}

    await session.commit()

    log = logger.bind(
        fee_id=outcome.fee.id,
        payment_id=payload.payment_id,
        payment_status=payload.status,
        fee_status=outcome.new_fee_status,
    )

    if outcome.transitioned and outcome.new_fee_status == FeeStatus.FIRST_PAID.value:
        log.info("fee_first_paid_access_released")
        background_tasks.add_task(notify_student_access_released, outcome.fee.student_external_id)
    elif outcome.transitioned and outcome.new_fee_status == FeeStatus.FULLY_PAID.value:
        log.info("fee_fully_paid")
        background_tasks.add_task(notify_student_fully_paid, outcome.fee.student_external_id)

    if outcome.payment_failed:
        log.warning("fee_payment_failed", kind=outcome.payment.kind)
        background_tasks.add_task(
            notify_coordinator_payment_failed,
            outcome.fee.coordinator_external_id,
            kind=outcome.payment.kind,
        )

    return {"ok": True, "fee_status": outcome.new_fee_status}
