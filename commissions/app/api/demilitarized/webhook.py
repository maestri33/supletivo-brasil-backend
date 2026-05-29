"""Webhook interno do asaas — status de payout (demilitarized: so dentro da plataforma).

O asaas notifica mudancas de status dos pagamentos em `internal_url_payout` com o
payload {payment_id, kind, external_id, status}. Como enviamos payment_id =
Payout.external_reference, casamos direto pela external_reference.

Esta rota e best-effort (acelera o status). A rede de SEGURANCA e o poll de
reconciliacao em services/payout.py — por isso ignoramos sem erro qualquer evento que
nao seja nosso (kind != pixkey, ou external_reference desconhecida). O asaas usa UMA
url de payout para pixkey (commissions) E qrcode (fees); ignorar o que nao e nosso e
intencional.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.payout import apply_payout_status
from app.utils.logging import get_logger

logger = get_logger("commissions.webhook")
router = APIRouter(prefix="/api/v1/webhook", tags=["webhook"])


class AsaasPayoutEvent(BaseModel):
    payment_id: str = Field(..., description="= Payout.external_reference")
    status: str = Field(..., description="Status do asaas (PAID/FAILED/AWAITING_BALANCE/...)")
    kind: str | None = Field(default=None, description="pixkey | qrcode | charge")
    external_id: str | None = Field(default=None, description="external_id do pagamento no asaas")


@router.post("/asaas-payout", summary="Recebe status de payout do asaas")
async def asaas_payout_webhook(
    event: AsaasPayoutEvent,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Atualiza o Payout (e suas comissoes) a partir do status enviado pelo asaas."""
    # Comissoes so pagam por pixkey. qrcode (fees) e charge (entrada) nao sao nossos.
    if event.kind is not None and event.kind != "pixkey":
        return {"ok": True, "ignored": f"kind={event.kind}"}

    payout = await apply_payout_status(
        db,
        external_reference=event.payment_id,
        asaas_status=event.status,
    )
    await db.commit()

    if payout is None:
        # external_reference desconhecida: provavelmente evento de outro consumidor. Ack.
        logger.info("webhook.payout_unmatched", payment_id=event.payment_id, status=event.status)
        return {"ok": True, "matched": False}

    return {"ok": True, "matched": True, "status": payout.status.value}
