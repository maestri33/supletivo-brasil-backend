"""Message — registro de mensagem enviada por canal (SQLAlchemy 2)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.contact import Contact

# Status validos para envio de mensagens
STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    contact_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("notify.contacts.id", ondelete="CASCADE", name="messages_contact_id_fkey"),
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    whatsapp_status: Mapped[str] = mapped_column(
        String(20), default=STATUS_PENDING, nullable=False,
    )
    email_status: Mapped[str] = mapped_column(
        String(20), default=STATUS_PENDING, nullable=False,
    )
    email_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tts_audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    contact: Mapped["Contact"] = relationship("Contact", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message {self.id} type={self.type}>"
