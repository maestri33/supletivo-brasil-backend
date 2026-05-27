"""Model Message — log de mensagens enviadas/recebidas via notify."""

from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class Message(Base, TimestampMixin):
    """Toda mensagem enviada ou webhook recebido do notify."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    message_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="ID retornado pelo notify no send_message",
    )

    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "auth.users.external_id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="messages_external_id_fkey",
        ),
        index=True,
        nullable=False,
    )

    direction: Mapped[str] = mapped_column(
        String(10),
        default="out",
        nullable=False,
        comment="out (envio) | in (webhook)",
    )

    channel: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="whatsapp | email | tts",
    )

    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
        comment="sent | delivered | read | failed",
    )

    event: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="message.sent | message.delivered | message.failed",
    )

    meta: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Dados extras do webhook",
    )

    def __repr__(self) -> str:
        return f"<Message #{self.message_id} {self.direction}>"
