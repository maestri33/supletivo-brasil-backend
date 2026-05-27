"""EducationalData — dados educacionais coletados na matrícula.

Tabela própria do schema `enrollment` (PRD §4 — "não delegados a outro
serviço"). Captura o que o TODO chama de "MUITO IMPORTANTE": último ano
estudado, quando foi, em que escola.

1:1 com Enrollment via `enrollment_id` (UNIQUE). Persistência mínima — sem
soft-delete, sem updated_at: o matriculando só envia uma vez na etapa.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EducationalData(Base):
    __tablename__ = "educational_data"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    enrollment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("enrollment.enrollments.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="FK 1:1 para enrollment.enrollments.id",
    )

    last_year_studied: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Último ano/série que o matriculando estudou (ex: 9 para 9º ano)",
    )

    last_year_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Data aproximada de quando foi o último ano estudado",
    )

    last_school: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Nome da escola onde cursou o último ano",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<EducationalData enrollment_id={self.enrollment_id} year={self.last_year_studied}>"
