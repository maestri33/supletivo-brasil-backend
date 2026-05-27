"""Prova do aluno — agendamento, correcao e tentativas.

O aluno agenda; o coordenador corrige. Reprovacao reabre o ciclo (nova tentativa).
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class ExamResult(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class StudentExam(Base, TimestampMixin):
    __tablename__ = "student_exams"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    student_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    subject: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        comment="Materia escolhida pelo aluno na hora do agendamento",
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Data e hora marcadas para a prova",
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Numero da tentativa (incrementa em cada nova prova)",
    )

    result: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="passed / failed (NULL = ainda nao corrigida)",
    )

    corrected_by_external_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="UUID do coordenador que corrigiu (external_id, sem FK)",
    )

    corrected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Observacoes do coordenador",
    )

    def __repr__(self) -> str:
        return (
            f"<StudentExam {self.id} subject={self.subject!r} "
            f"attempt={self.attempt_number} result={self.result!r}>"
        )
