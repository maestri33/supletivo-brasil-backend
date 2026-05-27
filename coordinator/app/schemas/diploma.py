"""Diploma schemas."""

from datetime import datetime

from app.schemas import APIModel


class DiplomaCreate(APIModel):
    """Schema para criar um diploma."""

    student_external_id: str
    coordinator_external_id: str
    notes: str | None = None


class DiplomaGraduateRequest(APIModel):
    """Schema para graduar um diploma (postar foto)."""

    diploma_photo_path: str


class DiplomaResponse(APIModel):
    """Schema de resposta com dados completos do diploma."""

    id: str
    student_external_id: str
    coordinator_external_id: str
    status: str
    history_path: str | None = None
    diploma_photo_path: str | None = None
    commission_triggered: bool = False
    notes: str | None = None
    graduated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DiplomaListResponse(APIModel):
    """Schema para listagem paginada de diplomas."""

    items: list[DiplomaResponse]
    total: int
