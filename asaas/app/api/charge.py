"""Rotas /charge — cobrancas PIX recebidas (Asaas inbound).

Fluxo:
  POST /charge/pix              cria cobranca PIX, retorna BR Code + QR image
  GET  /charge                  lista cobrancas
  GET  /charge/{payment_id}     consulta cobranca completa (com PIX)
  GET  /charge/{payment_id}/status   consulta apenas o status (light)
  POST /charge/{payment_id}/qr  re-busca QR Code no Asaas (refresh)
  DELETE /charge/{payment_id}   cancela cobranca (DELETE em Asaas)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..schemas import ChargeCreateRequest, ChargeResponse, responses_for
from ..services import charge as svc
from ..services import notifications
from ..services.customer import PayerData

router = APIRouter(prefix="/charge", tags=["charge"])


@router.post(
    "/pix",
    response_model=ChargeResponse,
    responses=responses_for(
        "invalid_amount",
        "invalid_due_date",
        "invalid_cpf_cnpj",
        "customer_required",
        "asaas_customer_create_failed",
        "asaas_charge_create_failed",
        "payment_id_already_exists",
        "asaas_api_key_not_set",
    ),
    summary="Criar cobranca PIX",
    response_description=(
        "Cobranca criada no Asaas; retorna BR Code (copia-e-cola) + QR Code (PNG base64). "
        "Notifica internal_url_charge com status=PENDING."
    ),
)
async def create_charge(
    body: ChargeCreateRequest,
    db: AsyncSession = Depends(get_session),
):
    """Cria cobranca PIX. Se external_id nao tem customer ainda, payer e obrigatorio."""
    payer = (
        PayerData(
            name=body.payer.name,
            cpf_cnpj=body.payer.cpf_cnpj,
            email=body.payer.email,
            mobile_phone=body.payer.mobile_phone,
        )
        if body.payer is not None
        else None
    )
    try:
        row = await svc.create(
            db,
            external_id=body.external_id,
            amount=body.amount,
            description=body.description,
            due_date=body.due_date,
            payment_id=body.payment_id,
            payer=payer,
        )
    except svc.PaymentError as e:
        await db.rollback()
        raise HTTPException(400, str(e)) from e
    await db.commit()
    await notifications.notify_internal(db, row)
    return svc.to_dict(row)


@router.get(
    "",
    response_model=list[ChargeResponse],
    summary="Listar cobrancas",
    response_description="Cobrancas PIX (kind=charge), do mais recente para o mais antigo.",
)
async def list_charges(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(
        default=None, description="PENDING | PAID | EXPIRED | CANCELLED | REFUNDED"
    ),
    external_id: str | None = Query(default=None, description="Filtra por customer external_id"),
    db: AsyncSession = Depends(get_session),
):
    try:
        rows = await svc.list_all(
            db, limit=limit, offset=offset, status=status, external_id=external_id
        )
    except svc.PaymentError as e:
        raise HTTPException(400, str(e)) from e
    return [svc.to_dict(r) for r in rows]


@router.get(
    "/{payment_id}",
    response_model=ChargeResponse,
    responses=responses_for(status_map={404: ["not_found"]}),
    summary="Consultar cobranca completa",
    response_description="Cobranca + PIX (BR Code e QR Code base64).",
)
async def get_charge(payment_id: str, db: AsyncSession = Depends(get_session)):
    row = await svc.get_by_payment_id(db, payment_id)
    if row is None:
        raise HTTPException(404, "not_found")
    return svc.to_dict(row)


@router.get(
    "/{payment_id}/status",
    responses=responses_for(status_map={404: ["not_found"]}),
    summary="Consultar status da cobranca",
    response_description="Apenas {payment_id, status, asaas_id} — versao leve para polling.",
)
async def get_charge_status(payment_id: str, db: AsyncSession = Depends(get_session)):
    row = await svc.get_by_payment_id(db, payment_id)
    if row is None:
        raise HTTPException(404, "not_found")
    return {
        "payment_id": row.payment_id,
        "status": row.status,
        "asaas_id": row.asaas_id,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.post(
    "/{payment_id}/qr",
    response_model=ChargeResponse,
    responses=responses_for(
        status_map={
            400: ["asaas_qr_fetch_failed", "asaas_api_key_not_set"],
            404: ["not_found"],
        }
    ),
    summary="Re-buscar QR Code no Asaas",
    response_description="Atualiza pix.payload e pix.encoded_image consultando o Asaas novamente.",
)
async def refresh_qr(payment_id: str, db: AsyncSession = Depends(get_session)):
    try:
        row = await svc.refresh_qr(db, payment_id)
    except svc.PaymentError as e:
        await db.rollback()
        if str(e) == "not_found":
            raise HTTPException(404, "not_found") from e
        raise HTTPException(400, str(e)) from e
    await db.commit()
    return svc.to_dict(row)


@router.delete(
    "/{payment_id}",
    response_model=ChargeResponse,
    responses=responses_for(
        status_map={
            400: ["cannot_cancel_status", "asaas_charge_delete_failed", "asaas_api_key_not_set"],
            404: ["not_found"],
        }
    ),
    summary="Cancelar cobranca",
    response_description="Cobranca cancelada localmente e no Asaas (DELETE /v3/payments/{id}).",
)
async def cancel_charge(payment_id: str, db: AsyncSession = Depends(get_session)):
    try:
        row = await svc.cancel(db, payment_id)
    except svc.PaymentError as e:
        await db.rollback()
        if str(e) == "not_found":
            raise HTTPException(404, "not_found") from e
        raise HTTPException(400, str(e)) from e
    await db.commit()
    await notifications.notify_internal(db, row)
    return svc.to_dict(row)
