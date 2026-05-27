"""Enrollment fees API v1 — manage student enrollment fees and payments."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session as get_db
from app.schemas import (
    EnrollmentFeeCreate,
    EnrollmentFeeListResponse,
    EnrollmentFeeResponse,
    EnrollmentFeePayRequest,
)
from app.services import (
    create_enrollment_fee,
    get_coordinator,
    list_enrollment_fees,
    pay_enrollment_fee,
)
from app.utils.logging import get_logger

logger = get_logger("coordinator.api.v1.enrollment_fees")
router = APIRouter(prefix="/enrollment-fees", tags=["enrollment_fees"])


@router.post("", response_model=EnrollmentFeeResponse, status_code=201)
async def create(
    body: EnrollmentFeeCreate,
    db: AsyncSession = Depends(get_db),
) -> EnrollmentFeeResponse:
    coord = await get_coordinator(db, body.coordinator_id)
    if not coord:
        raise HTTPException(status_code=404, detail="Coordinator not found")

    fee = await create_enrollment_fee(
        db,
        coordinator_id=body.coordinator_id,
        student_external_id=body.student_external_id,
        description=body.description,
        amount=body.amount,
        due_date=body.due_date,
    )
    await db.commit()
    return EnrollmentFeeResponse(
        id=fee.id,
        coordinator_id=fee.coordinator_id,
        student_external_id=fee.student_external_id,
        description=fee.description,
        amount=fee.amount,
        due_date=str(fee.due_date) if fee.due_date else None,
        status=fee.status.value,
        payment_external_id=fee.payment_external_id,
        notes=fee.notes,
        created_at=fee.created_at,
        updated_at=fee.updated_at,
    )


@router.get("", response_model=EnrollmentFeeListResponse)
async def list_all(
    coordinator_id: str | None = Query(None),
    student_external_id: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> EnrollmentFeeListResponse:
    items, total = await list_enrollment_fees(
        db,
        coordinator_id=coordinator_id,
        student_external_id=student_external_id,
        status=status,
        offset=offset,
        limit=limit,
    )
    return EnrollmentFeeListResponse(
        items=[
            EnrollmentFeeResponse(
                id=f.id,
                coordinator_id=f.coordinator_id,
                student_external_id=f.student_external_id,
                description=f.description,
                amount=f.amount,
                due_date=str(f.due_date) if f.due_date else None,
                status=f.status.value,
                payment_external_id=f.payment_external_id,
                notes=f.notes,
                created_at=f.created_at,
                updated_at=f.updated_at,
            )
            for f in items
        ],
        total=total,
    )


@router.post("/{fee_id}/pay", response_model=EnrollmentFeeResponse)
async def pay(
    fee_id: str,
    body: EnrollmentFeePayRequest,
    db: AsyncSession = Depends(get_db),
) -> EnrollmentFeeResponse:
    fee = await pay_enrollment_fee(db, fee_id, payment_external_id=body.payment_external_id or "")
    if not fee:
        raise HTTPException(status_code=404, detail="EnrollmentFee not found")
    await db.commit()
    return EnrollmentFeeResponse(
        id=fee.id,
        coordinator_id=fee.coordinator_id,
        student_external_id=fee.student_external_id,
        description=fee.description,
        amount=fee.amount,
        due_date=str(fee.due_date) if fee.due_date else None,
        status=fee.status.value,
        payment_external_id=fee.payment_external_id,
        notes=fee.notes,
        created_at=fee.created_at,
        updated_at=fee.updated_at,
    )
