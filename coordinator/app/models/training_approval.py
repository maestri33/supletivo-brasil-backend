"""Model TrainingApproval — aprovacao de conclusao de treinamento.

O coordenador aprova ou rejeita a conclusao de treinamento de um candidato.
"""

import enum
from uuid import uuid4

from sqlalchemy import Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class TrainingApproval(Base, TimestampMixin):
    __tablename__ = "training_approvals"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True, default=lambda: str(uuid4()))
    coordinator_id: Mapped[str] = mapped_column(
        UUIDStr, nullable=False, comment="FK logica -> coordinator.coordinators"
    )
    candidate_external_id: Mapped[str] = mapped_column(
        UUIDStr, nullable=False, comment="FK logica -> candidate.candidates"
    )
    training_external_id: Mapped[str] = mapped_column(
        UUIDStr, nullable=False, comment="FK logica -> training.materials ou trilha"
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="approval_status"),
        nullable=False,
        default=ApprovalStatus.pending,
        server_default="pending",
    )
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Motivo da aprovacao/rejeicao"
    )

    def __repr__(self) -> str:
        return f"<TrainingApproval {self.id} status={self.status.value}>"
