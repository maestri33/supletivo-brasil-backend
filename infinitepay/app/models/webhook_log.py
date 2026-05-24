"""Model SQLAlchemy: `infinitepay.webhook_logs`.

Auditoria de webhooks. Como o POST /webhook e publico externo (§5), guardamos
o maximo de origem possivel: source_ip (resolve X-Forwarded-For atras do proxy)
e user_agent.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class WebhookLog(Base):
    __tablename__ = "webhook_logs"
    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )

    external_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey(
            "auth.users.external_id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="webhook_logs_external_id_fkey",
        ),
        index=True,
        nullable=True,
    )
    direction: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    response: Mapped[dict | None] = mapped_column(JSON)
    source_ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
