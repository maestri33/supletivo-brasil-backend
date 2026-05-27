"""RateLimit model — controla janela e contagem horária por external_id."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RateLimit(Base):
    __tablename__ = "rate_limit"

    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "auth.users.external_id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="rate_limit_external_id_fkey",
        ),
        primary_key=True,
    )

    last_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    hourly_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    hourly_window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
