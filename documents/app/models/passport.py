"""Model Passport."""

from uuid import uuid4

from sqlalchemy import String, Date
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


class Passport(Base, TimestampMixin):
    __tablename__ = "passports"

    id: Mapped[str] = mapped_column(
        UUIDStr, primary_key=True, default=lambda: str(uuid4())
    )
    number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    expires_on: Mapped[str | None] = mapped_column(Date, nullable=True)
    issue_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    front_photo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    back_photo: Mapped[str | None] = mapped_column(String(500), nullable=True)
