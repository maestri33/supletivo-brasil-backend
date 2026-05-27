"""Diploma do aluno — emissao pelo coord + foto de retirada pelo aluno."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class StudentDiploma(Base, TimestampMixin):
    __tablename__ = "student_diplomas"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    student_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Um diploma por aluno",
    )

    issued_by_external_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="UUID do coordenador que emitiu (external_id, sem FK)",
    )

    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Quando o coord emitiu (certificado + historico)",
    )

    picked_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Quando o aluno registrou a retirada",
    )

    pickup_photo_external_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="UUID da foto da retirada no servico documents",
    )

    commission_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Quando a comissao do coordenador foi disparada (idempotencia)",
    )

    def __repr__(self) -> str:
        return f"<StudentDiploma {self.id} issued={self.issued_at} picked_up={self.picked_up_at}>"
