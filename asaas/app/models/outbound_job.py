"""Model SQLAlchemy: `asaas.outbound_jobs` (fila de saida com retry).

Caminho do dinheiro: cada notify interno (charge/payment/qrcode) e enfileirado na
mesma sessao do caller, entao commita atomico com a mudanca de estado. O worker
em `app/workers/outbound_queue.py` faz claim atomico e entrega com backoff.

Sem FK cross-schema (§4 da CONVENTION) — `external_id` aqui e o `payment_id` do
proprio asaas, usado pra correlacionar/observar.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class OutboundJob(Base):
    __tablename__ = "outbound_jobs"
    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    url: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    # Correlation ID (e.g., asaas payment_id "pay_xyz"). Nao e FK, nao precisa UUID.
    external_id: Mapped[str | None] = mapped_column(
        String,
        index=True,
        nullable=True,
    )

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=6)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
