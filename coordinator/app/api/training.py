"""API endpoints for training approvals."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session as get_db
from app.schemas import (
    TrainingApprovalCreate,
    TrainingApprovalListResponse,
    TrainingApprovalResponse,
    TrainingApprovalUpdate,
)
from app.services import (
    create_training_approval,
    get_coordinator,
    list_training_approvals,
    review_training_approval,
)
from app.utils.logging import get_logger

logger = get_logger("coordinator.api.training")
router = APIRouter(prefix="/training-approvals", tags=["training_approvals"])


@router.post("", response_model=TrainingApprovalResponse, status_code=201)
async def create(
    body: TrainingApprovalCreate,
    db: AsyncSession = Depends(get_db),
) -> TrainingApprovalResponse:
    # Validate coordinator exists
    coord = await get_coordinator(db, body.coordinator_id)
    if not coord:
        raise HTTPException(status_code=404, detail="Coordinator not found")

    ta = await create_training_approval(
        db,
        coordinator_id=body.coordinator_id,
        candidate_external_id=body.candidate_external_id,
        training_external_id=body.training_external_id,
    )
    await db.commit()
    return TrainingApprovalResponse(
        id=ta.id,
        coordinator_id=ta.coordinator_id,
        candidate_external_id=ta.candidate_external_id,
        training_external_id=ta.training_external_id,
        status=ta.status.value,
        reason=ta.reason,
        created_at=ta.created_at,
        updated_at=ta.updated_at,
    )


@router.get("", response_model=TrainingApprovalListResponse)
async def list(
    coordinator_id: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> TrainingApprovalListResponse:
    items, total = await list_training_approvals(
        db, coordinator_id=coordinator_id, status=status, offset=offset, limit=limit
    )
    return TrainingApprovalListResponse(
        items=[
            TrainingApprovalResponse(
                id=ta.id,
                coordinator_id=ta.coordinator_id,
                candidate_external_id=ta.candidate_external_id,
                training_external_id=ta.training_external_id,
                status=ta.status.value,
                reason=ta.reason,
                created_at=ta.created_at,
                updated_at=ta.updated_at,
            )
            for ta in items
        ],
        total=total,
    )


@router.patch("/{approval_id}", response_model=TrainingApprovalResponse)
async def review(
    approval_id: str,
    body: TrainingApprovalUpdate,
    db: AsyncSession = Depends(get_db),
) -> TrainingApprovalResponse:
    if body.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be 'approved' or 'rejected'")

    ta = await review_training_approval(
        db, approval_id, approved=body.status == "approved", reason=body.reason
    )
    if not ta:
        raise HTTPException(status_code=404, detail="TrainingApproval not found")
    await db.commit()
    return TrainingApprovalResponse(
        id=ta.id,
        coordinator_id=ta.coordinator_id,
        candidate_external_id=ta.candidate_external_id,
        training_external_id=ta.training_external_id,
        status=ta.status.value,
        reason=ta.reason,
        created_at=ta.created_at,
        updated_at=ta.updated_at,
    )
