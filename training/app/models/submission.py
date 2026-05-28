"""Model Submission — tentativa do trainee de responder uma materia.

Uma submissao representa UMA tentativa de resposta a UMA materia por UM trainee.
Pode haver varias submissoes (reenvio sem limite, TODO: "se nao aprovado pode
enviar novamente"). A nota e justificativa sao preenchidas assincronamente pela
IA via `services/grading.py`.

Status:
- `pending`  → recem-criada, aguardando IA
- `approved` → IA corrigiu, nota >= grade_pass_threshold (default 6)
- `rejected` → IA corrigiu, nota < grade_pass_threshold

Falha de IA mantem em `pending` (degrade gracioso, CONVENTION §14).
"""

import enum
from uuid import uuid4

from sqlalchemy import Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


class SubmissionStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Submission(Base, TimestampMixin):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(
        UUIDStr,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Referencia logica ao usuario no `auth` — sem FK cross-schema.
    external_id: Mapped[str] = mapped_column(
        UUIDStr,
        nullable=False,
        index=True,
        comment="UUID opaco do usuario (auth.users.external_id)",
    )

    # FK dentro do proprio schema training -> materials.id.
    material_id: Mapped[str] = mapped_column(
        UUIDStr,
        ForeignKey("materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    answer: Mapped[str] = mapped_column(Text, nullable=False, comment="Resposta do trainee")

    grade: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Nota 0-10 dada pela IA; null enquanto pending",
    )
    justification: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Justificativa da nota (invariante: toda nota gravada tem justificativa)",
    )

    status: Mapped[str] = mapped_column(
        Enum(
            SubmissionStatus,
            name="submission_status",
            values_callable=lambda e: [m.value for m in e],
            native_enum=False,
        ),
        nullable=False,
        default=SubmissionStatus.PENDING.value,
        index=True,
    )

    __table_args__ = (Index("submissions_external_material_idx", "external_id", "material_id"),)

    def __repr__(self) -> str:
        return (
            f"<Submission {self.id} mat={self.material_id} "
            f"user={self.external_id} status={self.status}>"
        )
