"""Endpoint authenticated/checkout — lead em fase de pagamento."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_checkout
from app.models import Checkout, Lead
from app.schemas import APIModel
from app.tools.qrcode import absolute_qr_url

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


class PixData(APIModel):
    """Dados PIX (so quando payment_method=pix)."""

    payment_id: str
    payload: str  # BR Code copia-e-cola
    qr_url: str  # URL absoluta do PNG
    due_date: date | None = None


class CheckoutGetResponse(APIModel):
    status: str
    message: str = "Realize seu pagamento para prosseguir"
    payment_method: str | None = None  # 'credit_card' | 'pix'
    provider: str | None = None  # 'infinitepay' | 'asaas'
    is_paid: bool = False

    # credit_card (infinitepay)
    checkout_url: str | None = None
    receipt_url: str | None = None
    capture_method: str | None = None
    installments: int | None = None

    # pix (asaas) — populado quando payment_method='pix'
    pix: PixData | None = None


@router.get(
    "/checkout",
    response_model=CheckoutGetResponse,
    summary="Verifica status e dados do checkout (cartao ou PIX)",
)
async def get_checkout(
    external_id: UUID = require_checkout(),
    session: AsyncSession = Depends(get_session),
):
    lead = await session.scalar(select(Lead).where(Lead.external_id == external_id))
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead nao encontrado")

    checkout = await session.scalar(select(Checkout).where(Checkout.external_id == external_id))

    pix_data: PixData | None = None
    if (
        checkout
        and checkout.payment_method == "pix"
        and checkout.qrcode_payload
        and checkout.provider_payment_id
    ):
        pix_data = PixData(
            payment_id=checkout.provider_payment_id,
            payload=checkout.qrcode_payload,
            qr_url=absolute_qr_url(checkout.qrcode_image) if checkout.qrcode_image else "",
            due_date=checkout.due_date,
        )

    is_paid = checkout.is_paid if checkout else False
    message = (
        "Pagamento confirmado! Acesso liberado."
        if is_paid
        else "Realize seu pagamento para prosseguir"
    )

    return CheckoutGetResponse(
        status=lead.status.value,
        message=message,
        payment_method=checkout.payment_method if checkout else None,
        provider=checkout.provider if checkout else None,
        is_paid=is_paid,
        checkout_url=checkout.checkout_url if checkout else None,
        receipt_url=checkout.receipt_url if checkout else None,
        capture_method=checkout.capture_method if checkout else None,
        installments=checkout.installments if checkout else None,
        pix=pix_data,
    )
