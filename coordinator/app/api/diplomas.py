"""API endpoints for diplomas."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session as get_db
from app.schemas import (
    DiplomaCreate,
    DiplomaGraduateRequest,
    DiplomaListResponse,
    DiplomaResponse,
)
from app.services import (
    create_diploma,
    graduate_student,
    list_diplomas,
)
from app.utils.logging import get_logger

logger = get_logger("coordinator.api.diplomas")
router = APIRouter(prefix="/diplomas", tags=["diplomas"])


@router.post("", response_model=DiplomaResponse, status_code=201)
async def create(
    body: DiplomaCreate,
    db: AsyncSession = Depends(get_db),
) -> DiplomaResponse:
    diploma = await create_diploma(
        db,
        student_external_id=body.student_external_id,
        coordinator_external_id=body.coordinator_external_id,
    )
    await db.commit()
    return DiplomaResponse(
        id=diploma.id,
        student_external_id=diploma.student_external_id,
        coordinator_external_id=diploma.coordinator_external_id,
        status=diploma.status,
        history_path=diploma.history_path,
        diploma_photo_path=diploma.diploma_photo_path,
        commission_triggered=diploma.commission_triggered,
        notes=diploma.notes,
        graduated_at=diploma.graduated_at,
        created_at=diploma.created_at,
        updated_at=diploma.updated_at,
    )


@router.get("", response_model=DiplomaListResponse)
async def list(
    student_external_id: str | None = Query(None),
    coordinator_external_id: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> DiplomaListResponse:
    items, total = await list_diplomas(
        db,
        student_external_id=student_external_id,
        coordinator_external_id=coordinator_external_id,
        status=status,
        offset=offset,
        limit=limit,
    )
    return DiplomaListResponse(
        items=[
            DiplomaResponse(
                id=d.id,
                student_external_id=d.student_external_id,
                coordinator_external_id=d.coordinator_external_id,
                status=d.status,
                history_path=d.history_path,
                diploma_photo_path=d.diploma_photo_path,
                commission_triggered=d.commission_triggered,
                notes=d.notes,
                graduated_at=d.graduated_at,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in items
        ],
        total=total,
    )


@router.post("/{diploma_id}/graduate", response_model=DiplomaResponse)
async def graduate(
    diploma_id: str,
    body: DiplomaGraduateRequest,
    db: AsyncSession = Depends(get_db),
) -> DiplomaResponse:
    diploma = await graduate_student(
        db,
        diploma_id,
        diploma_photo_path=body.diploma_photo_path,
    )
    if not diploma:
        raise HTTPException(status_code=404, detail="Diploma not found")
    await db.commit()
    return DiplomaResponse(
        id=diploma.id,
        student_external_id=diploma.student_external_id,
        coordinator_external_id=diploma.coordinator_external_id,
        status=diploma.status,
        history_path=diploma.history_path,
        diploma_photo_path=diploma.diploma_photo_path,
        commission_triggered=diploma.commission_triggered,
        notes=diploma.notes,
        graduated_at=diploma.graduated_at,
        created_at=diploma.created_at,
        updated_at=diploma.updated_at,
    )
