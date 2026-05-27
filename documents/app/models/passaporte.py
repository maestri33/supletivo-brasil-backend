"""Model Passaporte — passport."""

from uuid import uuid4

from sqlalchemy import String, Date
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


class Passaporte(Base, TimestampMixin):
    __tablename__ = "passaportes"

    id: Mapped[str] = mapped_column(
        UUIDStr,
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    numero: Mapped[str | None] = mapped_column(String(30), nullable=True)
    validade: Mapped[str | None] = mapped_column(Date, nullable=True)
    data_emissao: Mapped[str | None] = mapped_column(Date, nullable=True)
    foto_frente: Mapped[str | None] = mapped_column(String(500), nullable=True)
    foto_verso: Mapped[str | None] = mapped_column(String(500), nullable=True)
