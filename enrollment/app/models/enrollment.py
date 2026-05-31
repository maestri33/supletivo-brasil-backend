"""Enrollment — agregado de matrícula do lead pago.

Criado a partir do webhook `lead.completed`; orquestra a coleta de dados
(perfil, endereço, RG, dados educacionais, selfie) progredindo por status até a
liberação da plataforma, quando o usuário vira `student`.

Estado local mínimo: perfil/endereço/documentos/selfie vivem nos serviços donos
(profiles, address, documents). Aqui guardamos só o status da matrícula e os
vínculos (matriculando, promotor que indicou, hub).
"""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EnrollmentStatus(enum.StrEnum):
    """Etapas sequenciais da matrícula (espelha a lógica de funil do candidate)."""

    STARTED = "started"
    PROFILE = "profile"
    ADDRESS = "address"
    DOCUMENTS = "documents"
    EDUCATION = "education"
    SELFIE = "selfie"
    AWAITING_RELEASE = "awaiting_release"
    COMPLETED = "completed"


# Ordem do funil — base das transições/validação de avanço (milestones 2–5).
STATUS_ORDER: tuple[EnrollmentStatus, ...] = (
    EnrollmentStatus.STARTED,
    EnrollmentStatus.PROFILE,
    EnrollmentStatus.ADDRESS,
    EnrollmentStatus.DOCUMENTS,
    EnrollmentStatus.EDUCATION,
    EnrollmentStatus.SELFIE,
    EnrollmentStatus.AWAITING_RELEASE,
    EnrollmentStatus.COMPLETED,
)


class Enrollment(Base):
    __tablename__ = "enrollments"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        index=True,
        nullable=False,
        comment="UUID opaco do matriculando — 1 matrícula por usuário (referência lógica, sem FK §4)",
    )

    status: Mapped[str] = mapped_column(
        String(24),
        default=EnrollmentStatus.STARTED.value,
        nullable=False,
        index=True,
        comment="Etapa atual da matrícula",
    )

    promoter_external_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="UUID do promotor que indicou o lead",
    )

    hub_external_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="UUID do hub do promotor — resolvido quando o serviço hub existir",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Enrollment {self.external_id} status={self.status}>"
