"""API endpoints for exams."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session as get_db
from app.schemas import (
    ExamCreate,
    ExamGradeRequest,
    ExamListResponse,
    ExamResponse,
    ExamSubmitRequest,
)
from app.services import (
    create_exam,
    get_coordinator,
    grade_exam,
    list_exams,
    submit_exam,
)
from app.utils.logging import get_logger

logger = get_logger("coordinator.api.exams")
router = APIRouter(prefix="/exams", tags=["exams"])


@router.post("", response_model=ExamResponse, status_code=201)
async def create(
    body: ExamCreate,
    db: AsyncSession = Depends(get_db),
) -> ExamResponse:
    coord = await get_coordinator(db, body.coordinator_id)
    if not coord:
        raise HTTPException(status_code=404, detail="Coordinator not found")

    exam = await create_exam(
        db,
        coordinator_id=body.coordinator_id,
        student_external_id=body.student_external_id,
        training_external_id=body.training_external_id,
        max_score=body.max_score or 100,
    )
    await db.commit()
    return ExamResponse(
        id=exam.id,
        coordinator_id=exam.coordinator_id,
        student_external_id=exam.student_external_id,
        training_external_id=exam.training_external_id,
        status=exam.status.value,
        score=exam.score,
        max_score=exam.max_score,
        result_notes=exam.result_notes,
        ai_correction=exam.ai_correction,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
    )


@router.get("", response_model=ExamListResponse)
async def list(
    coordinator_id: str | None = Query(None),
    student_external_id: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> ExamListResponse:
    items, total = await list_exams(
        db,
        coordinator_id=coordinator_id,
        student_external_id=student_external_id,
        status=status,
        offset=offset,
        limit=limit,
    )
    return ExamListResponse(
        items=[
            ExamResponse(
                id=e.id,
                coordinator_id=e.coordinator_id,
                student_external_id=e.student_external_id,
                training_external_id=e.training_external_id,
                status=e.status.value,
                score=e.score,
                max_score=e.max_score,
                result_notes=e.result_notes,
                ai_correction=e.ai_correction,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in items
        ],
        total=total,
    )


@router.post("/{exam_id}/submit", response_model=ExamResponse)
async def submit(
    exam_id: str,
    body: ExamSubmitRequest,
    db: AsyncSession = Depends(get_db),
) -> ExamResponse:
    _ = body  # placeholder for future submission data
    exam = await submit_exam(db, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    await db.commit()
    return ExamResponse(
        id=exam.id,
        coordinator_id=exam.coordinator_id,
        student_external_id=exam.student_external_id,
        training_external_id=exam.training_external_id,
        status=exam.status.value,
        score=exam.score,
        max_score=exam.max_score,
        result_notes=exam.result_notes,
        ai_correction=exam.ai_correction,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
    )


@router.post("/{exam_id}/grade", response_model=ExamResponse)
async def grade(
    exam_id: str,
    body: ExamGradeRequest,
    db: AsyncSession = Depends(get_db),
) -> ExamResponse:
    exam = await grade_exam(
        db,
        exam_id,
        score=body.score,
        notes=body.result_notes,
    )
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    await db.commit()
    return ExamResponse(
        id=exam.id,
        coordinator_id=exam.coordinator_id,
        student_external_id=exam.student_external_id,
        training_external_id=exam.training_external_id,
        status=exam.status.value,
        score=exam.score,
        max_score=exam.max_score,
        result_notes=exam.result_notes,
        ai_correction=exam.ai_correction,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
    )
