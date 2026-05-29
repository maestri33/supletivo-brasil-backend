"""Mixins reutilizaveis para todos os models do schema training."""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import utcnow


class TimestampMixin:
    # default/onupdate em Python (utcnow): o valor ja' vem preenchido apos
    # flush/commit, sem expirar a coluna — evita lazy-load sincrono em sessao
    # async (MissingGreenlet). server_default cobre inserts via SQL cru/migracao.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )
