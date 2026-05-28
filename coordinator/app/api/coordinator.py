"""API endpoints for coordinator CRUD."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session as get_db
from app.models.coordinator import CoordinatorStatus
from app.schemas import (
    CoordinatorCreate,
    CoordinatorResponse,
    CoordinatorUpdate,
)
from app.services import (
    create_coordinator,
    get_coordinator,
    list_coordinators,
    update_coordinator_status,
)
from app.utils.logging import get_logger

logger = get_logger("coordinator.api")
router = APIRouter(prefix="/coordinators", tags=["coordinators"])


@router.post("", response_model=CoordinatorResponse, status_code=201)
async def create(
    body: CoordinatorCreate,
    db: AsyncSession = Depends(get_db),
) -> CoordinatorResponse:
    c = await create_coordinator(
        db,
        external_id=body.external_id,
        hub_external_id=body.hub_external_id,
    )
    await db.commit()
    return CoordinatorResponse(
        id=c.id,
        external_id=c.external_id,
        hub_external_id=c.hub_external_id,
        status=c.status.value,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("", response_model=dict)
async def list(
    hub_external_id: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items, total = await list_coordinators(
        db, hub_external_id=hub_external_id, status=status, offset=offset, limit=limit
    )
    return {
        "items": [
            CoordinatorResponse(
                id=c.id,
                external_id=c.external_id,
                hub_external_id=c.hub_external_id,
                status=c.status.value,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in items
        ],
        "total": total,
    }


@router.get("/{coordinator_id}", response_model=CoordinatorResponse)
async def get(
    coordinator_id: str,
    db: AsyncSession = Depends(get_db),
) -> CoordinatorResponse:
    c = await get_coordinator(db, coordinator_id)
    if not c:
        raise HTTPException(status_code=404, detail="Coordinator not found")
    return CoordinatorResponse(
        id=c.id,
        external_id=c.external_id,
        hub_external_id=c.hub_external_id,
        status=c.status.value,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.patch("/{coordinator_id}", response_model=CoordinatorResponse)
async def update(
    coordinator_id: str,
    body: CoordinatorUpdate,
    db: AsyncSession = Depends(get_db),
) -> CoordinatorResponse:
    if body.status:
        c = await update_coordinator_status(db, coordinator_id, CoordinatorStatus(body.status))
    else:
        c = await get_coordinator(db, coordinator_id)
    if not c:
        raise HTTPException(status_code=404, detail="Coordinator not found")
    await db.commit()
    return CoordinatorResponse(
        id=c.id,
        external_id=c.external_id,
        hub_external_id=c.hub_external_id,
        status=c.status.value,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )
