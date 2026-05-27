"""API endpoints for payment batch operations."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session as get_db
from app.schemas import (
    PaymentBatchListResponse,
    PaymentBatchResponse,
    TriggerProcessingRequest,
    TriggerProcessingResponse,
)
from app.services.commissions import PaymentBatchService, process_weekly_batch, submit_batch_for_payment
from app.utils.logging import get_logger
from datetime import datetime, UTC

logger = get_logger("commissions.api.batches")
router = APIRouter(prefix="/batches", tags=["payment_batches"])


@router.get("", response_model=PaymentBatchListResponse)
async def list_batches(
    status: str | None = Query(None, description="Filtrar por status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PaymentBatchListResponse:
    """Lista lotes de pagamento."""
    items, total = await PaymentBatchService.list(
        db, status=status, offset=offset, limit=limit
    )
    return PaymentBatchListResponse(
        items=[
            PaymentBatchResponse(
                id=b.id,
                week_of=b.week_of,
                total_cents=b.total_cents,
                bonus_cents=b.bonus_cents,
                status=b.status.value,
                pix_transaction_id=b.pix_transaction_id,
                created_at=b.created_at,
            )
            for b in items
        ],
        total=total,
    )


@router.get("/{batch_id}", response_model=PaymentBatchResponse)
async def get_batch(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
) -> PaymentBatchResponse:
    """Retorna detalhe de um lote de pagamento."""
    b = await PaymentBatchService.get(db, batch_id)
    if not b:
        raise HTTPException(status_code=404, detail="Payment batch not found")
    return PaymentBatchResponse(
        id=b.id,
        week_of=b.week_of,
        total_cents=b.total_cents,
        bonus_cents=b.bonus_cents,
        status=b.status.value,
        pix_transaction_id=b.pix_transaction_id,
        created_at=b.created_at,
    )


@router.post("/trigger-processing", response_model=TriggerProcessingResponse)
async def trigger_processing(
    body: TriggerProcessingRequest,
    db: AsyncSession = Depends(get_db),
) -> TriggerProcessingResponse:
    """Dispara processamento semanal de comissoes manualmente."""
    batch = await process_weekly_batch(
        db,
        week_of=body.week_of,
        force_reprocess=body.force_reprocess,
    )
    if not batch:
        return TriggerProcessingResponse(
            success=True,
            payment_batch_id=None,
            message="Nenhuma comissao pendente para processamento.",
            processed_at=datetime.now(UTC),
        )

    # Submit batch for payment via Asaas
    asaas_id = await submit_batch_for_payment(db, batch)

    await db.commit()

    return TriggerProcessingResponse(
        success=asaas_id is not None,
        payment_batch_id=batch.id,
        message=(
            f"Lote {batch.id} processado com sucesso. "
            f"Total: R$ {batch.total_cents / 100:.2f}. "
            f"Asaas ID: {asaas_id or 'pendente'}"
        ),
        processed_at=datetime.now(UTC),
    )
