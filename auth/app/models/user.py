import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db import metadata


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    metadata = metadata


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=_new_uuid,
    )
    external_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, unique=True, default=_new_uuid,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow,
    )

    roles = relationship("UserRole", back_populates="user")


class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=_new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        "user_id",
        Uuid, ForeignKey("users.external_id", ondelete="CASCADE"), nullable=False,
    )
    role: Mapped[str] = mapped_column(nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    user = relationship("User", back_populates="roles")
