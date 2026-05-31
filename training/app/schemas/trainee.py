"""Schemas do Trainee — leitura de estado e decisao do coordenador."""

from datetime import datetime

from pydantic import Field

from app.models.trainee import Trainee
from app.schemas import APIModel


class TraineeOut(APIModel):
    id: str
    external_id: str
    status: str
    coordinator_external_id: str | None
    coordinator_decision_at: datetime | None
    rejection_reason: str | None
    awaiting_interview_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, t: Trainee) -> "TraineeOut":
        return cls(
            id=str(t.id),
            external_id=str(t.external_id),
            status=t.status,
            coordinator_external_id=(
                str(t.coordinator_external_id) if t.coordinator_external_id else None
            ),
            coordinator_decision_at=t.coordinator_decision_at,
            rejection_reason=t.rejection_reason,
            awaiting_interview_at=t.awaiting_interview_at,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )


class CoordinatorRejectIn(APIModel):
    """Body do endpoint de rejeicao — motivo obrigatorio (TODO: "se rejeita texto com motivo")."""

    reason: str = Field(min_length=3, max_length=2000)
