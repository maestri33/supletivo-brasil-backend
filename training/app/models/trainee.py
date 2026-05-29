"""Model Trainee — estado do candidato dentro da trilha de treinamento.

Um Trainee e' criado na primeira submissao de uma materia e representa o estado
global do candidato dentro do funil do training (entre `candidate` e `promoter`):

- `training`           → cursando, ainda tem materia(s) nao aprovada(s)
- `awaiting_interview` → todas as materias aprovadas, aguardando coordenador
- `approved`           → coordenador aprovou; usuario foi promovido a `promoter`
- `rejected`           → coordenador rejeitou (com motivo)

Coordenador e' identificado por external_id (sem FK cross-schema; vive em `auth`).
"""

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


class TraineeStatus(enum.StrEnum):
    TRAINING = "training"
    AWAITING_INTERVIEW = "awaiting_interview"
    APPROVED = "approved"
    REJECTED = "rejected"


class Trainee(Base, TimestampMixin):
    __tablename__ = "trainees"

    id: Mapped[str] = mapped_column(
        UUIDStr,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    external_id: Mapped[str] = mapped_column(
        UUIDStr,
        nullable=False,
        unique=True,
        index=True,
        comment="UUID opaco do usuario (auth.users.external_id)",
    )

    status: Mapped[str] = mapped_column(
        Enum(
            TraineeStatus,
            name="trainee_status",
            values_callable=lambda e: [m.value for m in e],
            native_enum=False,
        ),
        nullable=False,
        default=TraineeStatus.TRAINING.value,
        index=True,
    )

    coordinator_external_id: Mapped[str | None] = mapped_column(UUIDStr, nullable=True)
    coordinator_decision_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Obrigatorio quando status=rejected"
    )

    awaiting_interview_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Trainee {self.id} user={self.external_id} status={self.status}>"
