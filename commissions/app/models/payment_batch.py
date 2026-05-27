"""Model PaymentBatch — lote semanal de pagamentos de comissoes."""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.commission import Commission

class PaymentBatchStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PaymentBatch(Base, TimestampMixin):
    __tablename__ = "payment_batches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    week_of: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True,
        comment="Data ISO da segunda-feira da semana de referencia (ex: 2026-05-25)",
    )

    total_cents: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Valor total do lote em centavos (comissoes + bonus)",
    )

    bonus_cents: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Valor total de bonus incluso no lote em centavos",
    )

    status: Mapped[PaymentBatchStatus] = mapped_column(
        Enum(
            PaymentBatchStatus,
            name="payment_batch_status",
            schema="commissions",
            create_type=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=PaymentBatchStatus.PENDING,
        nullable=False,
        index=True,
    )

    pix_transaction_id: Mapped[str | None] = mapped_column(
        String, nullable=True,
        comment="ID da transacao PIX no Asaas (transfer ou pix/transactions)",
    )

    asaas_transfer_id: Mapped[str | None] = mapped_column(
        String, nullable=True,
        comment="ID da transferencia no Asaas",
    )

    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Ultimo erro registrado na tentativa de pagamento",
    )

    # relationship
    commissions: Mapped[list["Commission"]] = relationship(
        "Commission", backref="payment_batch", lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<PaymentBatch {self.id} week={self.week_of} "
            f"total={self.total_cents} status={self.status}>"
        )
