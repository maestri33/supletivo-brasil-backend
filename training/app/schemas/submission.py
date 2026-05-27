"""Schemas da Submission (entrada do trainee, leitura, listagem)."""

from datetime import datetime

from pydantic import Field

from app.models.submission import Submission
from app.schemas import APIModel


class SubmissionCreate(APIModel):
    """Body do POST /api/v1/submissions — material_id + resposta do trainee."""

    material_id: str = Field(min_length=1)
    answer: str = Field(min_length=1, max_length=20000)


class SubmissionOut(APIModel):
    id: str
    external_id: str
    material_id: str
    answer: str
    grade: float | None
    justification: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, s: Submission) -> "SubmissionOut":
        return cls(
            id=str(s.id),
            external_id=str(s.external_id),
            material_id=str(s.material_id),
            answer=s.answer,
            grade=s.grade,
            justification=s.justification,
            status=s.status,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )


class SubmissionListResponse(APIModel):
    total: int
    submissions: list[SubmissionOut]


class MaterialProgressOut(APIModel):
    """Progresso do trainee em UMA materia: ultima submissao e status."""

    material_id: str
    status: str
    grade: float | None = None
    justification: str | None = None
    attempts: int = 0
    last_submission_id: str | None = None
    last_submission_at: datetime | None = None
