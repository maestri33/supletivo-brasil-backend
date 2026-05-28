"""Contact — canal/contacto do usuário externo (SQLAlchemy 2)."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.message import Message


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "auth.users.external_id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="contacts_external_id_fkey",
        ),
        unique=True,
        index=True,
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        unique=True,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="contact",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Contact {self.external_id}>"
