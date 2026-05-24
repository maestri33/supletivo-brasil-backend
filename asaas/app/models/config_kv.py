"""Model SQLAlchemy: `asaas.config` (key/value, uma linha por chave)."""

from sqlalchemy import Column, DateTime, String, Text

from ..db import Base, utcnow


class ConfigKV(Base):
    """Single-row key/value config. One row per key."""

    __tablename__ = "config"
    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
