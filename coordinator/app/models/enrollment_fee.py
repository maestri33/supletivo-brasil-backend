"""Model EnrollmentFee — taxas de matricula gerenciadas pelo coordenador.

O coordenador cadastra e paga taxas de matricula dos alunos.
"""

import enum
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Date, Enum, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


class FeeStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    cancelled = "cancelled"


class EnrollmentFee(Base, TimestampMixin):
    __tablename__ = "enrollment_fees"

    id: Mapped[str] = mapped_column(
        UUIDStr, primary_key=True, default=lambda: str(uuid4())
    )
    coordinator_id: Mapped[str] = mapped_column(
        UUIDStr, nullable=False, comment="FK logica -> coordinator.coordinators"
    )
    student_external_id: Mapped[str] = mapped_column(
        UUIDStr, nullable=False, comment="FK logica -> student.students"
    )
    description: Mapped[str] = mapped_column(
        String(300), nullable=False, comment="Descricao da taxa"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Valor da taxa"
    )
    due_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="Data de vencimento"
    )
    status: Mapped[FeeStatus] = mapped_column(
        Enum(FeeStatus, name="fee_status"),
        nullable=False,
        default=FeeStatus.pending,
        server_default="pending",
    )
    payment_external_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="ID do pagamento no gateway (Asaas)"
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Observacoes"
    )

    def __repr__(self) -> str:
        return f"<EnrollmentFee {self.id} amount={self.amount} status={self.status.value}>"
