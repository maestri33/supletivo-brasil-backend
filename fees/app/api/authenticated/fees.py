"""Endpoints autenticados de taxas — só o coordenador do polo (§5).

Todos exigem JWT válido com a role de coordenador (ver `dependencies`).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import get_asaas_client, get_current_coordinator
from app.exceptions import NotFound
from app.integrations.asaas import AsaasClient
from app.models import Fee, FeePayment
from app.schemas import FeeCreate, FeePaymentRead, FeeRead
from app.services import fee_service

router = APIRouter(prefix="/api/v1/authenticated/fees", tags=["fees"])


def _to_read(fee: Fee, payments: list[FeePayment]) -> FeeRead:
    return FeeRead(
        id=fee.id,
        student_external_id=fee.student_external_id,
        coordinator_external_id=fee.coordinator_external_id,
        status=fee.status,
        description=fee.description,
        payments=[FeePaymentRead.model_validate(p) for p in payments],
        created_at=fee.created_at,
        updated_at=fee.updated_at,
    )


@router.post(
    "",
    response_model=FeeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar taxa de matrícula (2 payouts PIX: à vista + agendado)",
)
async def create_fee(
    body: FeeCreate,
    coordinator_id: UUID = Depends(get_current_coordinator),
    asaas: AsaasClient = Depends(get_asaas_client),
    session: AsyncSession = Depends(get_session),
) -> FeeRead:
    fee, payments = await fee_service.create_fee(
        session,
        asaas,
        student_external_id=str(body.student_external_id),
        coordinator_external_id=str(coordinator_id),
        description=body.description,
        upfront=body.upfront,
        scheduled=body.scheduled,
    )
    return _to_read(fee, payments)


@router.get("", response_model=list[FeeRead], summary="Listar taxas")
async def list_fees(
    fee_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _coordinator_id: UUID = Depends(get_current_coordinator),
    session: AsyncSession = Depends(get_session),
) -> list[FeeRead]:
    fees = await fee_service.list_fees(session, status=fee_status, limit=limit, offset=offset)
    out: list[FeeRead] = []
    for fee in fees:
        payments = await fee_service.load_payments(session, fee.id)
        out.append(_to_read(fee, payments))
    return out


@router.get(
    "/student/{student_external_id}",
    response_model=FeeRead,
    summary="Última taxa de um aluno",
)
async def get_fee_by_student(
    student_external_id: UUID,
    _coordinator_id: UUID = Depends(get_current_coordinator),
    session: AsyncSession = Depends(get_session),
) -> FeeRead:
    fee = await fee_service.get_latest_fee_by_student(session, str(student_external_id))
    if fee is None:
        raise NotFound("Nenhuma taxa para este aluno")
    payments = await fee_service.load_payments(session, fee.id)
    return _to_read(fee, payments)


@router.get("/{fee_id}", response_model=FeeRead, summary="Obter taxa por id")
async def get_fee(
    fee_id: UUID,
    _coordinator_id: UUID = Depends(get_current_coordinator),
    session: AsyncSession = Depends(get_session),
) -> FeeRead:
    fee = await fee_service.get_fee(session, str(fee_id))
    if fee is None:
        raise NotFound("Taxa não encontrada")
    payments = await fee_service.load_payments(session, fee.id)
    return _to_read(fee, payments)
