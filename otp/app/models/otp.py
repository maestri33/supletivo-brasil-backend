"""OTPLog model — records every OTP operation (SQLAlchemy 2)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OTPLog(Base):
    __tablename__ = "otp_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "auth.users.external_id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="otp_logs_external_id_fkey",
        ),
        index=True,
        nullable=False,
    )

    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20),
        default="generated",
        nullable=False,
        comment="generated | sent | verified | expired | failed",
    )

    # Tentativas inválidas de verificação. Quando atinge otp_max_attempts,
    # o status vira "failed" com failure_reason="invalid_code".
    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    # Categoriza falha pra observabilidade. Preenchido quando status in
    # (failed, expired). Valores: notify_down | notify_permanent | invalid_code
    # | expired | inactive.
    failure_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)

    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
