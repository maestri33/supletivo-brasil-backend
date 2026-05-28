"""Training approval schemas."""

from datetime import datetime

from app.schemas import APIModel


class TrainingApprovalCreate(APIModel):
    """Schema para criar uma solicitação de aprovação de treinamento."""

    coordinator_id: str
    candidate_external_id: str
    training_external_id: str


class TrainingApprovalUpdate(APIModel):
    """Schema para aprovar/rejeitar um treinamento."""

    status: str
    reason: str | None = None


class TrainingApprovalResponse(APIModel):
    """Schema de resposta com dados completos da aprovação."""

    id: str
    coordinator_id: str
    candidate_external_id: str
    training_external_id: str
    status: str
    reason: str | None = None
    created_at: datetime
    updated_at: datetime


class TrainingApprovalListResponse(APIModel):
    """Schema para listagem paginada de aprovações."""

    items: list[TrainingApprovalResponse]
    total: int
