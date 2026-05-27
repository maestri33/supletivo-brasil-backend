"""Exam schemas."""

from datetime import datetime

from app.schemas import APIModel


class ExamCreate(APIModel):
    """Schema para criar uma prova."""

    coordinator_id: str
    student_external_id: str
    training_external_id: str
    max_score: int = 100


class ExamSubmitRequest(APIModel):
    """Schema para submeter uma prova para correção."""

    ai_correction: str | None = None


class ExamGradeRequest(APIModel):
    """Schema para corrigir (atribuir nota) uma prova."""

    score: int
    result_notes: str | None = None


class ExamResponse(APIModel):
    """Schema de resposta com dados completos da prova."""

    id: str
    coordinator_id: str
    student_external_id: str
    training_external_id: str
    status: str
    score: int | None = None
    max_score: int = 100
    result_notes: str | None = None
    ai_correction: str | None = None
    created_at: datetime
    updated_at: datetime


class ExamListResponse(APIModel):
    """Schema para listagem paginada de provas."""

    items: list[ExamResponse]
    total: int
