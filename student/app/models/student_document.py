"""Referencia local a um documento enviado pelo aluno.

A foto/PDF vive no servico `documents` (§7). Aqui guardamos somente o
external_id do documento + tipo + status da validacao IA.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class DocumentType(StrEnum):
    """Tipos de documento que o aluno envia (PRD student §4)."""

    MILITARY_SERVICE = "military_service"  # so' homens (regra do PRD §8.3)
    CERTIFICATE = "certificate"            # certificado do ultimo ano (obrigatorio)
    TRANSCRIPT = "transcript"              # historico do ultimo ano (obrigatorio)
    BLOOD_TYPE = "blood_type"              # tipo sanguineo (foto)
    ADDRESS_PROOF = "address_proof"        # comprovante de endereco (foto)
    ID_CARD = "id_card"                    # RG (foto) — obrigatorio
    BIRTH_CERTIFICATE = "birth_certificate"  # certidao (nasc/casamento)


REQUIRED_DOCUMENT_TYPES: tuple[DocumentType, ...] = (
    DocumentType.CERTIFICATE,
    DocumentType.TRANSCRIPT,
    DocumentType.ID_CARD,
)


class ValidationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class StudentDocument(Base, TimestampMixin):
    """Documento enviado pelo aluno e seu estado de validacao IA."""

    __tablename__ = "student_documents"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    student_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Aluno dono do documento (FK intra-schema)",
    )

    document_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
        comment="Tipo do documento (DocumentType)",
    )

    document_external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="UUID opaco do registro no servico documents",
    )

    validation_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ValidationStatus.PENDING.value,
        comment="Status da validacao IA (ValidationStatus)",
    )

    validation_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Resultado bruto da IA (descricao, confidence, motivo)",
    )

    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp da ultima decisao da IA",
    )

    __table_args__ = (
        UniqueConstraint("student_id", "document_type", name="student_documents_student_type_key"),
    )

    def __repr__(self) -> str:
        return (
            f"<StudentDocument {self.id} type={self.document_type!r} "
            f"validation={self.validation_status!r}>"
        )
