"""Schemas Pydantic v2 do servico student."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.student import StudentStatus


class PromoteRequest(BaseModel):
    """Coordenador promove um matriculado a aluno (enrollment->student)."""

    external_id: UUID
    study_platform: dict[str, Any] = Field(default_factory=dict)


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: UUID
    status: StudentStatus
    study_platform: dict[str, Any]
    created_at: datetime
    updated_at: datetime
