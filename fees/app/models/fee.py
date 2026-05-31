"""Model `fees.fee` — a taxa de matrícula de um aluno (student).

Uma taxa é composta de dois pagamentos PIX por QR Code (ver `FeePayment`):
o coordenador do polo paga uma parte à vista e agenda a outra. O status da
taxa é **derivado** dos status dos dois pagamentos (ver `services/fee_service`).

`student_external_id` é opaco (UUID emitido por outro serviço) — sem FK
cross-schema, mesmo princípio do `asaas` (o identificador é fornecido por quem
chama a API, não é validado contra `auth.users` aqui).
"""

import enum
from uuid import uuid4

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class FeeStatus(str, enum.Enum):
    """Estado da taxa, derivado dos dois pagamentos.

    PENDING     — criada; nenhuma parte paga ainda.
    FIRST_PAID  — parte à vista paga → **acesso à plataforma liberável**.
    FULLY_PAID  — ambas as partes pagas.
    FAILED      — a parte à vista falhou no Asaas (taxa não avança).
    CANCELLED   — cancelada manualmente.
    """

    PENDING = "PENDING"
    FIRST_PAID = "FIRST_PAID"
    FULLY_PAID = "FULLY_PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Fee(Base, TimestampMixin):
    __tablename__ = "fee"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    # UUID do aluno (opaco, sem FK — fornecido por quem chama, §4 / padrão asaas).
    student_external_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), index=True, nullable=False
    )
    # UUID do coordenador que criou a taxa (vem do JWT).
    coordinator_external_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=FeeStatus.PENDING.value, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Fee {self.id} student={self.student_external_id} status={self.status}>"
