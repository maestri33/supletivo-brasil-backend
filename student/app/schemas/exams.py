"""Schemas Pydantic v2 — provas do aluno."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.student_exam import ExamResult


class ExamScheduleRequest(BaseModel):
    """POST /students/me/exams — aluno agenda nova prova."""

    subject: str = Field(min_length=1, max_length=80)
    scheduled_at: datetime


class ExamGradeRequest(BaseModel):
    """PATCH /students/{id}/exams/{exam_id} — coordenador lanca resultado."""

    result: ExamResult
    notes: str | None = Field(default=None, max_length=500)


class StudentExamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    subject: str
    scheduled_at: datetime
    attempt_number: int
    result: ExamResult | None
    corrected_by_external_id: UUID | None
    corrected_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class StudentExamList(BaseModel):
    items: list[StudentExamRead]
    total: int
