"""API endpoints for student documents."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session as get_db
from app.schemas import (
    StudentDocumentCreate,
    StudentDocumentListResponse,
    StudentDocumentResponse,
)
from app.services import (
    create_student_document,
    list_student_documents,
    submit_document_to_institution,
)
from app.utils.logging import get_logger

logger = get_logger("coordinator.api.documents")
router = APIRouter(prefix="/documents", tags=["student_documents"])


@router.post("", response_model=StudentDocumentResponse, status_code=201)
async def create(
    body: StudentDocumentCreate,
    db: AsyncSession = Depends(get_db),
) -> StudentDocumentResponse:
    doc = await create_student_document(
        db,
        student_external_id=body.student_external_id,
        coordinator_external_id=body.coordinator_external_id,
        document_type=body.document_type,
        description=body.description,
        file_path=body.file_path,
    )
    await db.commit()
    return StudentDocumentResponse(
        id=doc.id,
        student_external_id=doc.student_external_id,
        coordinator_external_id=doc.coordinator_external_id,
        document_type=doc.document_type,
        description=doc.description,
        file_path=doc.file_path,
        submitted_to_institution=doc.submitted_to_institution,
        submitted_at=doc.submitted_at,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("", response_model=StudentDocumentListResponse)
async def list(
    student_external_id: str | None = Query(None),
    coordinator_external_id: str | None = Query(None),
    document_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> StudentDocumentListResponse:
    items, total = await list_student_documents(
        db,
        student_external_id=student_external_id,
        coordinator_external_id=coordinator_external_id,
        document_type=document_type,
        offset=offset,
        limit=limit,
    )
    return StudentDocumentListResponse(
        items=[
            StudentDocumentResponse(
                id=d.id,
                student_external_id=d.student_external_id,
                coordinator_external_id=d.coordinator_external_id,
                document_type=d.document_type,
                description=d.description,
                file_path=d.file_path,
                submitted_to_institution=d.submitted_to_institution,
                submitted_at=d.submitted_at,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in items
        ],
        total=total,
    )


@router.post("/{document_id}/submit", response_model=StudentDocumentResponse)
async def submit(
    document_id: str,
    db: AsyncSession = Depends(get_db),
) -> StudentDocumentResponse:
    doc = await submit_document_to_institution(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="StudentDocument not found")
    await db.commit()
    return StudentDocumentResponse(
        id=doc.id,
        student_external_id=doc.student_external_id,
        coordinator_external_id=doc.coordinator_external_id,
        document_type=doc.document_type,
        description=doc.description,
        file_path=doc.file_path,
        submitted_to_institution=doc.submitted_to_institution,
        submitted_at=doc.submitted_at,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
