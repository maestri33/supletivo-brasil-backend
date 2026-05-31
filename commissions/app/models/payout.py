"""Model Payout — a "solicitacao de pagamento" por beneficiario (a fila do payout).

UMA linha por beneficiario por lote semanal: agrega as comissoes+bonus daquela
pessoa num UNICO pagamento Pix (o desenho do dono: "1 pagamento por pessoa").

`external_reference` = chave de idempotencia, grudada em todas as comissoes do payout
e enviada ao asaas como `payment_id`. Formato: {ordinal-sexta}_{MM}_{AAAA}_{external_id}.

Quem detem a fila PESADA (retry da transferencia, espera de saldo via AWAITING_BALANCE)
e o app `asaas`. Aqui guardamos a solicitacao, empurramos pro asaas (idempotente pelo
payment_id) e rastreamos o status final via webhook OU consulta. SEM FK cross-schema (§4).
"""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class PayoutStatus(str, enum.Enum):
    QUEUED = "queued"                      # criado; ainda nao empurrado pro asaas
    SUBMITTED = "submitted"                # asaas aceitou (temos asaas_id); aguardando status final
    AWAITING_BALANCE = "awaiting_balance"  # asaas sem saldo: espera (espelha o asaas)
    PAID = "paid"                          # asaas confirmou pagamento
    FAILED = "failed"                      # falha definitiva (ex: pixkey_not_found, max tentativas)
    CANCELLED = "cancelled"                # cancelado manualmente


class Payout(Base, TimestampMixin):
    __tablename__ = "payouts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    # Idempotencia. = payment_id enviado ao asaas. {ord-sexta}_{MM}_{AAAA}_{external_id}.
    external_reference: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
        comment="Chave de idempotencia do payout; enviada ao asaas como payment_id",
    )

    # Beneficiario (promotor ou coordenador). UUID opaco = external_id da pixkey no asaas.
    # SEM FK cross-schema (§4 da CONVENTION).
    recipient_external_id: Mapped[UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
        comment="UUID do beneficiario (tambem e o external_id da pixkey cadastrada no asaas)",
    )
    recipient_role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Funcao do beneficiario: promoter | coordinator",
    )

    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Soma das comissoes+bonus deste beneficiario no lote, em centavos",
    )

    week_of: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="Segunda-feira ISO da semana de referencia (ex: 2026-05-25)",
    )

    payment_batch_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "payment_batches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="payouts_payment_batch_id_fkey",
        ),
        nullable=True,
        index=True,
        comment="Lote semanal que originou este payout",
    )

    status: Mapped[PayoutStatus] = mapped_column(
        Enum(
            PayoutStatus,
            name="payout_status",
            schema="commissions",
            create_type=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=PayoutStatus.QUEUED,
        nullable=False,
        index=True,
    )

    # Espelho do estado no asaas
    asaas_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="UUID da transferencia/transacao no asaas (PaymentResponse.asaas_id)",
    )
    asaas_status: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="Ultimo status recebido do asaas, verbatim (SUBMITTED/PAID/AWAITING_BALANCE/...)",
    )

    # Fila leve: retry do PUSH/reconciliacao com o asaas (NAO da transferencia — isso e do asaas).
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Quando o worker deve tentar empurrar/reconciliar de novo (NULL = pronto agora)",
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Payout {self.id} ref={self.external_reference} "
            f"amount={self.amount_cents} status={self.status}>"
        )
