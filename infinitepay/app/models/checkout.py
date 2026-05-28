"""Model SQLAlchemy: `infinitepay.checkouts`."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class Checkout(Base):
    __tablename__ = "checkouts"
    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )

    # external_id: UUID opaco referenciando o usuário no serviço auth (§4 da
    # CONVENTION). Sem FK cross-schema; validação via HTTP quando necessário.
    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=False),
        unique=True,
        index=True,
        nullable=False,
    )

    checkout_url: Mapped[str] = mapped_column(Text)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)

    receipt_url: Mapped[str | None] = mapped_column(Text)
    installments: Mapped[int | None] = mapped_column(Integer)
    invoice_slug: Mapped[str | None] = mapped_column(String(128))
    capture_method: Mapped[str | None] = mapped_column(String(32))
    transaction_nsu: Mapped[str | None] = mapped_column(String(128))

    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    response_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
