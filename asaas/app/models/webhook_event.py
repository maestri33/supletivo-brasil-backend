"""Model SQLAlchemy: `asaas.webhook_event` (payloads brutos recebidos do Asaas).

O POST /webhook/ e publico externo (§5): guardamos source_ip (resolve
X-Forwarded-For atras do proxy) e user_agent da origem.
"""

from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from ..db import Base, utcnow


class WebhookEvent(Base):
    """Raw webhook payloads received from Asaas."""

    __tablename__ = "webhook_event"
    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    received_at = Column(DateTime(timezone=True), default=utcnow, index=True)
    event = Column(String, index=True)
    payload = Column(Text)
    forwarded_ok = Column(Boolean, default=False)
    forwarded_at = Column(DateTime(timezone=True), nullable=True)
    source_ip = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
