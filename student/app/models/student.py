"""Model Student + enum de status do funil do aluno."""

from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class StudentStatus(StrEnum):
    """Status do funil do aluno (spec student/TODO).

    O enum completo e definido desde ja para evitar migracao de tipo a cada
    milestone; o Milestone 1 so grava AWAITING_DOCUMENTS na promocao.
    """

    AWAITING_DOCUMENTS = "awaiting_documents"
    DOCUMENTS_UNDER_REVIEW = "documents_under_review"
    EXAM_RELEASED = "exam_released"
    EXAM_SCHEDULED = "exam_scheduled"
    EXAM_FAILED = "exam_failed"
    AWAITING_DOCUMENTATION_DISPATCH = "awaiting_documentation_dispatch"
    PENDING = "pending"
    AWAITING_DIPLOMA_ISSUANCE = "awaiting_diploma_issuance"
    AWAITING_PICKUP = "awaiting_pickup"
    VETERAN = "veteran"


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        index=True,
        nullable=False,
        comment="UUID opaco do usuário (referência lógica, sem FK §4)",
    )

    status: Mapped[StudentStatus] = mapped_column(
        SAEnum(StudentStatus, name="student_status", native_enum=False, length=40),
        default=StudentStatus.AWAITING_DOCUMENTS,
        nullable=False,
        index=True,
    )

    # Dados da plataforma de estudo informados pelo coordenador na promocao.
    # JSONB no Postgres; JSON generico no sqlite (testes).
    study_platform: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )

    def __repr__(self) -> str:
        return f"<Student {self.external_id} {self.status.value}>"
