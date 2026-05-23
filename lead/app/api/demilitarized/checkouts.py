"""CRUD de checkouts — endpoints internos entre serviços."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Checkout
from app.schemas import APIModel

router = APIRouter(prefix="/api/v1/demilitarized", tags=["demilitarized"])


class CheckoutOut(APIModel):
    id: int
    external_id: UUID
    checkout_url: str | None = None
    receipt_url: str | None = None
    invoice_slug: str | None = None
    transaction_nsu: str | None = None
    capture_method: str | None = None
    installments: int | None = None
    payment_method: str | None = None
    provider: str | None = None
    provider_payment_id: str | None = None
    qrcode_payload: str | None = None
    qrcode_image: str | None = None
    due_date: date | None = None
    is_paid: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class CheckoutPatch(APIModel):
    checkout_url: str | None = None
    receipt_url: str | None = None
    is_paid: bool | None = None
    capture_method: str | None = None
    installments: int | None = None


def _to_out(c: Checkout) -> CheckoutOut:
    return CheckoutOut(
        id=c.id,
        external_id=c.external_id,
        checkout_url=c.checkout_url,
        receipt_url=c.receipt_url,
        invoice_slug=c.invoice_slug,
        transaction_nsu=c.transaction_nsu,
        capture_method=c.capture_method,
        installments=c.installments,
        payment_method=c.payment_method,
        provider=c.provider,
        provider_payment_id=c.provider_payment_id,
        qrcode_payload=c.qrcode_payload,
        qrcode_image=c.qrcode_image,
        due_date=c.due_date,
        is_paid=c.is_paid,
        created_at=c.created_at.isoformat() if c.created_at else None,
        updated_at=c.updated_at.isoformat() if c.updated_at else None,
    )


@router.get("/checkouts", response_model=list[CheckoutOut], summary="Lista todos os checkouts")
async def list_checkouts(session: AsyncSession = Depends(get_session)):
    result = await session.scalars(select(Checkout).order_by(Checkout.created_at.desc()))
    return [_to_out(c) for c in result.all()]


@router.get(
    "/checkouts/{external_id}",
    response_model=CheckoutOut,
    summary="Busca checkout por external_id",
)
async def get_checkout(external_id: UUID, session: AsyncSession = Depends(get_session)):
    c = await session.scalar(select(Checkout).where(Checkout.external_id == external_id))
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Checkout nao encontrado")
    return _to_out(c)


@router.patch(
    "/checkouts/{external_id}",
    response_model=CheckoutOut,
    summary="Atualiza checkout",
)
async def patch_checkout(
    external_id: UUID,
    payload: CheckoutPatch,
    session: AsyncSession = Depends(get_session),
):
    c = await session.scalar(select(Checkout).where(Checkout.external_id == external_id))
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Checkout nao encontrado")

    for field in ("checkout_url", "receipt_url", "is_paid", "capture_method", "installments"):
        val = getattr(payload, field)
        if val is not None:
            setattr(c, field, val)

    await session.commit()
    await session.refresh(c)
    return _to_out(c)


@router.delete(
    "/checkouts/{external_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove checkout",
)
async def delete_checkout(external_id: UUID, session: AsyncSession = Depends(get_session)):
    c = await session.scalar(select(Checkout).where(Checkout.external_id == external_id))
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Checkout nao encontrado")
    await session.delete(c)
    await session.commit()
