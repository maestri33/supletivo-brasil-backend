"""Diploma — diploma do aluno, histórico e foto de formatura.

Ao postar a foto do aluno recebendo diploma, o ciclo se encerra e o
coordenador recebe comissão (integração com o serviço commissions).
"""

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class DiplomaStatus(enum.StrEnum):
    PENDING = "pending"
    ISSUED = "issued"
    GRADUATED = "graduated"


class Diploma(Base, TimestampMixin):
    __tablename__ = "diplomas"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    student_external_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey(
            "auth.users.external_id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="diplomas_student_external_id_fkey",
        ),
        nullable=False,
        index=True,
        comment="UUID do aluno formando",
    )

    coordinator_external_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey(
            "auth.users.external_id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="diplomas_coordinator_external_id_fkey",
        ),
        nullable=False,
        index=True,
        comment="UUID do coordenador responsável",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=DiplomaStatus.PENDING.value,
        nullable=False,
        index=True,
        comment="Status: pending, issued, graduated",
    )

    history_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Caminho relativo do histórico escolar",
    )

    diploma_photo_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Caminho relativo da foto do aluno com diploma",
    )

    commission_triggered: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Se a comissão do coordenador já foi acionada",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Observações sobre a formatura",
    )

    graduated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Quando o ciclo foi concluído (foto postada)",
    )

    def __repr__(self) -> str:
        return f"<Diploma {self.id} status={self.status}>"
