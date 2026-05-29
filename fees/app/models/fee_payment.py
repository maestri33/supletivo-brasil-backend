"""Model `fees.fee_payment` — um dos dois pagamentos PIX de uma taxa.

Cada taxa (`Fee`) tem exatamente dois: `upfront` (à vista) e `scheduled`
(agendado). Ambos são **payouts** de QR Code (BR Code copia-e-cola) feitos via
serviço `asaas` (`POST /payment/qrcode` e `/payment/qrcode/scheduled`).

`payment_id` é o identificador idempotente que o fees envia ao asaas e que o
asaas devolve no webhook interno — é a **chave de correlação** do callback de
status (o asaas não manda `external_id` em payouts de QR Code).

Referência ao `Fee` é por valor (`fee_id`), sem FK declarada — mesmo princípio
do `asaas` (evita acoplamento de schema e mantém os testes portáveis).
"""

import enum
from datetime import date
from uuid import uuid4

from sqlalchemy import Date, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

# Status de payout espelhados do asaas (string, não enum no DB — portável):
#   PENDING -> (SCHEDULED|QUEUED) -> SUBMITTING -> SUBMITTED -> PAID
#   ramos: AWAITING_BALANCE, FAILED, CANCELLED, NEEDS_RECONCILE
#   SUBMIT_ERROR é marcador local (falha de rede ao chamar o asaas na criação).
PAID_STATUS = "PAID"
FAILED_STATUSES = frozenset({"FAILED", "CANCELLED"})


class FeePaymentKind(str, enum.Enum):
    UPFRONT = "upfront"
    SCHEDULED = "scheduled"


class FeePayment(Base, TimestampMixin):
    __tablename__ = "fee_payment"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    fee_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # upfront | scheduled
    # Idempotency-Key enviada ao asaas e chave de correlação do webhook.
    payment_id: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    qrcode_payload: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False, index=True)
    asaas_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<FeePayment {self.payment_id} kind={self.kind} status={self.status}>"
