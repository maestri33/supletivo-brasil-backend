"""EnrollmentEvent — registra cada bifurcação recebida do lead.

Stub auditivo: persiste todo POST recebido em `${WEBHOOK_ENROLLMENT_URL}/{external_id}`
para que a lógica de matrícula futura possa processar os eventos sem perdas.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EnrollmentEvent(Base):
    __tablename__ = "enrollment_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "auth.users.external_id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="enrollment_events_external_id_fkey",
        ),
        index=True,
        nullable=False,
    )

    event: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    promoter_external_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Quando lógica de matrícula real processar (futuro)",
    )

    def __repr__(self) -> str:
        return f"<EnrollmentEvent {self.event} for {self.external_id}>"
