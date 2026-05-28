"""Model WorkCard — work permit (Carteira de Trabalho)."""

from uuid import uuid4

from sqlalchemy import String, Date
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


class WorkCard(Base, TimestampMixin):
    __tablename__ = "work_cards"

    id: Mapped[str] = mapped_column(
        UUIDStr, primary_key=True, default=lambda: str(uuid4())
    )
    number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    series: Mapped[str | None] = mapped_column(String(20), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    issue_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    front_photo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    back_photo: Mapped[str | None] = mapped_column(String(500), nullable=True)
