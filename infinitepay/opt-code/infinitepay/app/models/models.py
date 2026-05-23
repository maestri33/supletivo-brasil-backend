from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, ForeignKey, Integer, MetaData, String, Table, Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


_settings = get_settings()


class Base(DeclarativeBase):
    metadata = MetaData(schema=_settings.database_schema)


# Shadow auth.users — necessário pro SQLAlchemy resolver FK cross-schema.
auth_users = Table(
    "users",
    Base.metadata,
    Column("external_id", PG_UUID(as_uuid=True), primary_key=True),
    schema="auth",
)


class Config(Base):
    __tablename__ = "config"
    id: Mapped[int] = mapped_column(primary_key=True)

    handle: Mapped[str | None] = mapped_column(String(128))
    price: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str | None] = mapped_column(String(255))
    redirect_url: Mapped[str | None] = mapped_column(Text)
    backend_webhook: Mapped[str | None] = mapped_column(Text)

    public_api_url: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Checkout(Base):
    __tablename__ = "checkouts"
    id: Mapped[int] = mapped_column(primary_key=True)

    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "auth.users.external_id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="checkouts_external_id_fkey",
        ),
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


class WebhookLog(Base):
    __tablename__ = "webhook_logs"
    id: Mapped[int] = mapped_column(primary_key=True)

    external_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "auth.users.external_id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="webhook_logs_external_id_fkey",
        ),
        index=True,
        nullable=True,
    )
    direction: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    response: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutboundJob(Base):
    __tablename__ = "outbound_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    external_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "auth.users.external_id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="outbound_jobs_external_id_fkey",
        ),
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
