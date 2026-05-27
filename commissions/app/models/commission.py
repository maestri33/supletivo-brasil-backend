"""Model Commission — comissoes para promotores e coordenadores."""

import enum
from uuid import UUID

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class CommissionStatus(str, enum.Enum):
    PENDING = "pending"          # aguardando processamento semanal
    PROCESSED = "processed"      # incluida em lote de pagamento
    PAID = "paid"                # PIX enviado com sucesso
    FAILED = "failed"            # PIX falhou
    CANCELLED = "cancelled"      # cancelada manualmente


class Commission(Base, TimestampMixin):
    __tablename__ = "commissions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Quem recebe (FK para auth.users via external_id)
    recipient_external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "auth.users.external_id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="commissions_recipient_external_id_fkey",
        ),
        index=True,
        nullable=False,
        comment="UUID do usuario que recebe a comissao (promotor ou coordenador)",
    )

    recipient_role: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
        comment="Funcao do receptor: promoter, coordinator",
    )

    # Origem da comissao
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
        comment="Tipo de entidade que originou: lead, student_completion",
    )
    source_external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        index=True,
        nullable=False,
        comment="UUID externo da entidade de origem (lead.external_id ou student.external_id)",
    )

    amount_cents: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Valor da comissao em centavos",
    )

    status: Mapped[CommissionStatus] = mapped_column(
        Enum(
            CommissionStatus,
            name="commission_status",
            schema="commissions",
            create_type=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=CommissionStatus.PENDING,
        nullable=False,
        index=True,
    )

    payment_batch_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "commissions.payment_batches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="commissions_payment_batch_id_fkey",
        ),
        nullable=True,
        index=True,
        comment="Lote de pagamento ao qual esta comissao pertence",
    )

    def __repr__(self) -> str:
        return (
            f"<Commission {self.id} role={self.recipient_role} "
            f"amount={self.amount_cents} status={self.status}>"
        )
