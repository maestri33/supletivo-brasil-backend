"""StudentDocument — documentos do aluno coletados e enviados à instituição.

O coordenador é responsável por reunir os documentos do aluno (RG, CPF,
histórico, etc.) e enviá-los à instituição de ensino.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class StudentDocument(Base, TimestampMixin):
    __tablename__ = "student_documents"

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
            name="student_documents_student_external_id_fkey",
        ),
        nullable=False,
        index=True,
        comment="UUID do aluno dono do documento",
    )

    coordinator_external_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey(
            "auth.users.external_id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="student_documents_coordinator_external_id_fkey",
        ),
        nullable=False,
        index=True,
        comment="UUID do coordenador que coletou/enviou",
    )

    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Tipo do documento: rg, cpf, history, diploma, other",
    )

    description: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="Descrição do documento",
    )

    file_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Caminho relativo do arquivo no storage",
    )

    submitted_to_institution: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Se já foi enviado à instituição",
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Quando foi enviado à instituição",
    )

    def __repr__(self) -> str:
        return (
            f"<StudentDocument {self.id} type={self.document_type!r} "
            f"submitted={self.submitted_to_institution}>"
        )
