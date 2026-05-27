"""Model CNH — driver license."""

from uuid import uuid4

from sqlalchemy import String, Date
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


class CNH(Base, TimestampMixin):
    __tablename__ = "cnh"

    id: Mapped[str] = mapped_column(
        UUIDStr,
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    numero: Mapped[str | None] = mapped_column(String(30), nullable=True)
    categoria: Mapped[str | None] = mapped_column(String(5), nullable=True)
    data_nascimento: Mapped[str | None] = mapped_column(Date, nullable=True)
    validade: Mapped[str | None] = mapped_column(Date, nullable=True)
    registro_nacional: Mapped[str | None] = mapped_column(String(30), nullable=True)
    foto_frente: Mapped[str | None] = mapped_column(String(500), nullable=True)
    foto_verso: Mapped[str | None] = mapped_column(String(500), nullable=True)
