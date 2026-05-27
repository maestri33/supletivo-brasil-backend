"""Model Exam — provas aplicadas pelo coordenador.

O coordenador aplica provas, corrige e posta resultados.
"""

import enum
from uuid import uuid4

from sqlalchemy import Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


class ExamStatus(str, enum.Enum):
    created = "created"
    in_progress = "in_progress"
    submitted = "submitted"
    graded = "graded"


class Exam(Base, TimestampMixin):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True, default=lambda: str(uuid4()))
    coordinator_id: Mapped[str] = mapped_column(
        UUIDStr, nullable=False, comment="FK logica -> coordinator.coordinators"
    )
    student_external_id: Mapped[str] = mapped_column(
        UUIDStr, nullable=False, comment="FK logica -> student.students"
    )
    training_external_id: Mapped[str] = mapped_column(
        UUIDStr, nullable=False, comment="FK logica -> training associada"
    )
    status: Mapped[ExamStatus] = mapped_column(
        Enum(ExamStatus, name="exam_status"),
        nullable=False,
        default=ExamStatus.created,
        server_default="created",
    )
    score: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Nota do aluno (0-100)"
    )
    max_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100", comment="Nota maxima"
    )
    result_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Observacoes da correcao"
    )
    ai_correction: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Correcao gerada por IA"
    )

    def __repr__(self) -> str:
        return f"<Exam {self.id} status={self.status.value} score={self.score}>"
