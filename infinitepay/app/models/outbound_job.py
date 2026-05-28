"""Model SQLAlchemy: `infinitepay.outbound_jobs` (fila de saida com retry)."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class OutboundJob(Base):
    __tablename__ = "outbound_jobs"
    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    url: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    # external_id: UUID opaco referenciando o usuário no serviço auth (§4 da
    # CONVENTION). Sem FK cross-schema.
    external_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=False),
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
