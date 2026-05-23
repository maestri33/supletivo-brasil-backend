"""Rotas /payment.

Pixkey:
  POST /payment             imediato
  POST /payment/scheduled   agendado (default 08:00 America/Sao_Paulo)

QR Code:
  POST /payment/qrcode/analyze     analisa BR Code sem pagar
  POST /payment/qrcode             paga agora
  POST /payment/qrcode/scheduled   agenda QR estatico

Regras de QR:
  - QR com valor fixo nao aceita amount diferente.
  - QR sem valor fixo exige amount.
  - QR dinamico nao pode ser agendado.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import async_session_maker, get_session
from ..schemas import PaymentResponse, QRCodeAnalyzeResponse, responses_for
from ..services import payment as svc
from ..utils.brcode import analyze as analyze_brcode

router = APIRouter(prefix="/payment", tags=["payment"])


# ---------- shared body bases ----------


class _PixkeyBase(BaseModel):
    external_id: str = Field(..., description="external_id da pixkey registrada")
    amount: float = Field(..., gt=0, description="Valor em BRL")
    payment_id: str | None = Field(
        default=None, description="ID idempotente opcional fornecido pelo cliente"
    )
    description: str | None = Field(default=None, description="Descricao enviada ao Asaas")


class _QRCodeBase(BaseModel):
    qrcode_payload: str = Field(..., min_length=20, description="BR Code copia-e-cola")
    amount: float | None = Field(
        default=None,
        gt=0,
        description="Valor em BRL. Obrigatorio qdo QR nao tem valor fixo; proibido se divergir.",
    )
    payment_id: str | None = Field(
        default=None, description="ID idempotente opcional fornecido pelo cliente"
    )
    description: str | None = Field(default=None, description="Descricao enviada ao Asaas")


class _ScheduledMixin(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    hour: int | None = Field(
        default=None, ge=0, le=23, description="Hora local America/Sao_Paulo. Default 08."
    )
    minute: int | None = Field(
        default=None, ge=0, le=59, description="Minuto local America/Sao_Paulo. Default 00."
    )


class PixkeyImediateRequest(_PixkeyBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "external_id": "diandra_celular",
                "amount": 0.03,
                "payment_id": "diandra_salario_202604",
                "description": "Pagamento salario abril/2026",
            }
        }
    )


class PixkeyScheduledRequest(_PixkeyBase, _ScheduledMixin):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "external_id": "diandra_celular",
                "amount": 0.03,
                "date": "2026-04-24",
                "hour": 16,
                "minute": 15,
                "payment_id": "diandra_agendado_20260424",
            }
        }
    )


class QRCodeImediateRequest(_QRCodeBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "qrcode_payload": "00020126360014br.gov.bcb.pix0114+554299938406952040000530398654040.025802BR...",  # noqa: E501
                "description": "Pagamento via QR Code",
            }
        }
    )


class QRCodeScheduledRequest(_QRCodeBase, _ScheduledMixin):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "qrcode_payload": "00020126360014br.gov.bcb.pix0114+554299938406952040000530398654040.025802BR...",  # noqa: E501
                "date": "2026-04-24",
                "hour": 16,
                "minute": 15,
            }
        }
    )


class QRCodeAnalyzeRequest(BaseModel):
    qrcode_payload: str = Field(..., min_length=20, description="BR Code copia-e-cola")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "qrcode_payload": "00020126360014br.gov.bcb.pix0114+554299938406952040000530398654040.025802BR..."  # noqa: E501
            }
        }
    )


# ---------- helpers ----------


async def _submit_bg(payment_id: str):
    async with async_session_maker() as s:
        row = await svc.get_by_payment_id(s, payment_id)
        if row and row.status == "QUEUED":
            await svc.submit_one(s, row)
            await s.commit()


async def _create_and_respond(
    row,
    db: AsyncSession,
    bg: BackgroundTasks,
):
    await db.commit()
    await svc._notify_internal(db, row)
    if row.status == "QUEUED":
        bg.add_task(_submit_bg, row.payment_id)
    return svc.to_dict(row)


# ---------- routes ----------


@router.post(
    "",
    response_model=PaymentResponse,
    responses=responses_for("pixkey_not_found", "invalid_amount", "payment_id_already_exists"),
    summary="Criar pagamento imediato por pixkey",
    response_description="Payment criado, notificado como QUEUED e submetido em background.",
)
async def create_pixkey_imediate(
    body: PixkeyImediateRequest,
    bg: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    """Cria uma transferencia Pix imediata para uma pixkey previamente cadastrada."""
    try:
        row = await svc.create_pixkey(
            db,
            body.external_id,
            body.amount,
            payment_id=body.payment_id,
            description=body.description,
        )
    except svc.PaymentError as e:
        await db.rollback()
        raise HTTPException(400, str(e)) from e
    return await _create_and_respond(row, db, bg)


@router.post(
    "/scheduled",
    response_model=PaymentResponse,
    responses=responses_for(
        "pixkey_not_found", "invalid_amount", "invalid_date", "payment_id_already_exists"
    ),
    summary="Agendar pagamento por pixkey",
    response_description="Payment agendado, sera submetido automaticamente no horario informado.",
)
async def create_pixkey_scheduled(
    body: PixkeyScheduledRequest,
    bg: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    """Agenda transferencia Pix para a data/hora local America/Sao_Paulo."""
    try:
        row = await svc.create_pixkey(
            db,
            body.external_id,
            body.amount,
            payment_id=body.payment_id,
            description=body.description,
            schedule_date=body.date,
            hour=body.hour,
            minute=body.minute,
        )
    except svc.PaymentError as e:
        await db.rollback()
        raise HTTPException(400, str(e)) from e
    return await _create_and_respond(row, db, bg)


@router.post(
    "/qrcode",
    response_model=PaymentResponse,
    responses=responses_for(
        "invalid_qrcode_payload",
        "qrcode_amount_required",
        "qrcode_fixed_amount_mismatch",
        "invalid_amount",
        "payment_id_already_exists",
    ),
    summary="Criar pagamento imediato por QR Code",
    response_description="Payment criado, validado pelas regras de QR e submetido em background.",
)
async def create_qrcode_imediate(
    body: QRCodeImediateRequest,
    bg: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    """Paga um BR Code copia-e-cola. Use `/payment/qrcode/analyze` quando houver duvida."""
    try:
        row = await svc.create_qrcode(
            db,
            body.qrcode_payload,
            body.amount,
            payment_id=body.payment_id,
            description=body.description,
        )
    except svc.PaymentError as e:
        await db.rollback()
        raise HTTPException(400, str(e)) from e
    return await _create_and_respond(row, db, bg)


@router.post(
    "/qrcode/analyze",
    response_model=QRCodeAnalyzeResponse,
    summary="Analisar QR Code sem pagar",
    response_description="Analise TLV/BR Code com tipo, valor, chave/URL dinamica e avisos.",
)
def analyze_qrcode(body: QRCodeAnalyzeRequest):
    """Inspeciona o BR Code antes de decidir se `amount` e permitido ou obrigatorio."""
    return analyze_brcode(body.qrcode_payload)


@router.post(
    "/qrcode/scheduled",
    response_model=PaymentResponse,
    responses=responses_for(
        "invalid_qrcode_payload",
        "qrcode_amount_required",
        "qrcode_fixed_amount_mismatch",
        "dynamic_qrcode_scheduling_not_supported",
        "invalid_amount",
        "invalid_date",
        "payment_id_already_exists",
    ),
    summary="Agendar pagamento por QR Code",
    response_description="Payment agendado para QR estatico; QR dinamico e recusado.",
)
async def create_qrcode_scheduled(
    body: QRCodeScheduledRequest,
    bg: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    """Agenda pagamento de QR Code estatico. QR dinamico e bloqueado por seguranca."""
    try:
        row = await svc.create_qrcode(
            db,
            body.qrcode_payload,
            body.amount,
            payment_id=body.payment_id,
            description=body.description,
            schedule_date=body.date,
            hour=body.hour,
            minute=body.minute,
        )
    except svc.PaymentError as e:
        await db.rollback()
        raise HTTPException(400, str(e)) from e
    return await _create_and_respond(row, db, bg)


@router.get(
    "",
    response_model=list[PaymentResponse],
    summary="Listar pagamentos",
    response_description="Lista paginada de payments, ordenada do mais recente para o mais antigo.",
)
async def list_payments(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    kind: str | None = Query(default=None, description="Filtra por tipo: pixkey ou qrcode"),
    status: str | None = Query(
        default=None, description="Filtra por status: SCHEDULED, PAID, etc."
    ),
    db: AsyncSession = Depends(get_session),
):
    try:
        rows = await svc.list_all(db, limit=limit, offset=offset, kind=kind, status=status)
    except svc.PaymentError as e:
        raise HTTPException(400, str(e)) from e
    return [svc.to_dict(r) for r in rows]


@router.get(
    "/awaiting-balance",
    response_model=list[PaymentResponse],
    summary="Listar pagamentos aguardando saldo",
    response_description=(
        "Pagamentos com status AWAITING_BALANCE, do mais recente para o mais antigo."
    ),
    openapi_extra={
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "example": [
                            {
                                "payment_id": "pay_a1b2c3d4e5f6a7b8",
                                "kind": "pixkey",
                                "external_id": "diandra_celular",
                                "qrcode_payload": None,
                                "amount": 0.03,
                                "description": "Pagamento salario",
                                "scheduled_for": None,
                                "status": "AWAITING_BALANCE",
                                "asaas_id": "bc46e593-0a72-4495-a2f8-b4ad499791c0",
                                "last_error": "insufficient_balance",
                                "created_at": "2026-04-24T17:35:24",
                                "updated_at": "2026-04-24T17:35:36",
                            }
                        ]
                    }
                }
            }
        }
    },
)
async def list_awaiting_balance(db: AsyncSession = Depends(get_session)):
    return [svc.to_dict(r) for r in await svc.list_awaiting_balance(db)]


@router.get(
    "/awaiting-balance/sum",
    summary="Soma dos pagamentos aguardando saldo",
    response_description="Total em BRL e contagem de payments em AWAITING_BALANCE.",
)
async def sum_awaiting_balance(db: AsyncSession = Depends(get_session)):
    return await svc.sum_awaiting_balance(db)


@router.post(
    "/{payment_id}/cancel",
    response_model=PaymentResponse,
    responses=responses_for(
        status_map={
            400: ["cannot_cancel_status", "asaas_cancel_failed"],
            404: ["not_found"],
        }
    ),
    summary="Cancelar pagamento",
    response_description="Payment cancelado localmente ou no Asaas, conforme status atual.",
)
async def cancel_payment(payment_id: str, db: AsyncSession = Depends(get_session)):
    """Cancela pagamento pendente/agendado localmente; se submetido, chama Asaas."""
    try:
        row = await svc.cancel(db, payment_id)
        await db.commit()
    except svc.PaymentError as e:
        await db.rollback()
        if str(e) == "not_found":
            raise HTTPException(404, "not_found") from e
        raise HTTPException(400, str(e)) from e
    return svc.to_dict(row)


@router.delete(
    "/{payment_id}",
    response_model=PaymentResponse,
    responses=responses_for(
        status_map={
            400: ["cannot_delete_status"],
            404: ["not_found"],
        }
    ),
    summary="Deletar pagamento agendado ou aguardando saldo",
    response_description=(
        "Cancela localmente payments em SCHEDULED ou AWAITING_BALANCE. Dispara notificacao interna."
    ),
)
async def delete_payment(payment_id: str, db: AsyncSession = Depends(get_session)):
    """Remove (cancela) pagamento. So permitido para SCHEDULED e AWAITING_BALANCE."""
    try:
        row = await svc.delete_one(db, payment_id)
        await db.commit()
    except svc.PaymentError as e:
        await db.rollback()
        if str(e) == "not_found":
            raise HTTPException(404, "not_found") from e
        raise HTTPException(400, str(e)) from e
    return svc.to_dict(row)


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    responses=responses_for(status_map={404: ["not_found"]}),
    summary="Consultar pagamento",
    response_description="Status e metadados do payment.",
)
async def get_payment(payment_id: str, db: AsyncSession = Depends(get_session)):
    row = await svc.get_by_payment_id(db, payment_id)
    if row is None:
        raise HTTPException(404, "not_found")
    return svc.to_dict(row)
