"""Schemas Pydantic v2 — diploma do aluno."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DiplomaPickupRequest(BaseModel):
    """POST /students/me/diploma/pickup — aluno registra retirada com foto."""

    pickup_photo_external_id: UUID


class StudentDiplomaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    issued_by_external_id: UUID | None
    issued_at: datetime | None
    picked_up_at: datetime | None
    pickup_photo_external_id: UUID | None
    commission_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime
