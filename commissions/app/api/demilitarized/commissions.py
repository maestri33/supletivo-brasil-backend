"""Commission, PaymentBatch, and Processing endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas import (
    CommissionCreate,
    CommissionListResponse,
    CommissionResponse,
    PaymentBatchListResponse,
    PaymentBatchResponse,
    TriggerProcessingRequest,
    TriggerProcessingResponse,
)
from app.services import (
    create_commission,
    get_commission,
    list_commissions,
    get_payment_batch,
    list_payment_batches,
    process_weekly_batch,
    submit_batch_for_payment,
)

router = APIRouter(prefix="/api/v1", tags=["commissions"])


# ---------------------------------------------------------------------------
# Commission endpoints
# ---------------------------------------------------------------------------


@router.get("/commissions", response_model=CommissionListResponse)
async def list_commissions_endpoint(
    recipient_external_id: str | None = Query(None, description="Filter by recipient external ID"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Max items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    session: AsyncSession = Depends(get_session),
) -> CommissionListResponse:
    """List commissions with optional filters."""
    recipient_uuid: UUID | None = None
    if recipient_external_id:
        recipient_uuid = UUID(recipient_external_id)

    items, total = await list_commissions(
        session,
        recipient_external_id=recipient_uuid,
        status=status,
        offset=offset,
        limit=limit,
    )
    return CommissionListResponse(
        items=[CommissionResponse.model_validate(c) for c in items],
        total=total,
    )


@router.get("/commissions/{commission_id}", response_model=CommissionResponse)
async def get_commission_endpoint(
    commission_id: int,
    session: AsyncSession = Depends(get_session),
) -> CommissionResponse:
    """Get a single commission by ID."""
    commission = await get_commission(session, commission_id)
    if commission is None:
        from app.main import _DomainError

        raise _DomainError("Comissão não encontrada", status_code=404)
    return CommissionResponse.model_validate(commission)


@router.post("/commissions", response_model=CommissionResponse, status_code=201)
async def create_commission_endpoint(
    body: CommissionCreate,
    session: AsyncSession = Depends(get_session),
) -> CommissionResponse:
    """Create a new commission."""
    commission = await create_commission(
        session,
        recipient_external_id=UUID(body.recipient_external_id),
        recipient_role=body.recipient_role,
        source_type=body.source_type,
        source_external_id=UUID(body.source_external_id),
        amount_cents=body.amount_cents,
    )
    await session.commit()
    await session.refresh(commission)
    return CommissionResponse.model_validate(commission)


# ---------------------------------------------------------------------------
# Payment Batch endpoints
# ---------------------------------------------------------------------------


@router.get("/payment-batches", response_model=PaymentBatchListResponse)
async def list_payment_batches_endpoint(
    limit: int = Query(50, ge=1, le=200, description="Max items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    session: AsyncSession = Depends(get_session),
) -> PaymentBatchListResponse:
    """List payment batches."""
    items, total = await list_payment_batches(session, offset=offset, limit=limit)
    return PaymentBatchListResponse(
        items=[PaymentBatchResponse.model_validate(b) for b in items],
        total=total,
    )


@router.get("/payment-batches/{batch_id}", response_model=PaymentBatchResponse)
async def get_payment_batch_endpoint(
    batch_id: int,
    session: AsyncSession = Depends(get_session),
) -> PaymentBatchResponse:
    """Get a single payment batch by ID."""
    batch = await get_payment_batch(session, batch_id)
    if batch is None:
        from app.main import _DomainError

        raise _DomainError("Lote de pagamento não encontrado", status_code=404)
    return PaymentBatchResponse.model_validate(batch)


# ---------------------------------------------------------------------------
# Processing endpoints
# ---------------------------------------------------------------------------


@router.post("/processing/trigger", response_model=TriggerProcessingResponse)
async def trigger_processing_endpoint(
    body: TriggerProcessingRequest,
    session: AsyncSession = Depends(get_session),
) -> TriggerProcessingResponse:
    """Manually trigger weekly commission processing."""
    from datetime import datetime, timezone

    batch = await process_weekly_batch(
        session,
        week_of=body.week_of,
        force_reprocess=body.force_reprocess,
    )

    if batch is None:
        # No pending commissions or batch already exists — still a valid response
        return TriggerProcessingResponse(
            success=True,
            payment_batch_id=None,
            message="Nenhuma comissão pendente para processar ou lote já existe para esta semana.",
            processed_at=datetime.now(timezone.utc),
        )

    # Submit batch for payment via Asaas
    await submit_batch_for_payment(session, batch)
    await session.commit()
    await session.refresh(batch)

    return TriggerProcessingResponse(
        success=batch.status.value != "failed",
        payment_batch_id=batch.id,
        message=f"Lote {batch.id} processado com status {batch.status.value}.",
        processed_at=datetime.now(timezone.utc),
    )
