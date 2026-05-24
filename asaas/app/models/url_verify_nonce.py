"""Model SQLAlchemy: `asaas.url_verify_nonce` (nonces de validacao de URL)."""

from sqlalchemy import Column, DateTime, String, Text

from ..db import Base, utcnow


class UrlVerifyNonce(Base):
    """Nonces issued during external-URL validation."""

    __tablename__ = "url_verify_nonce"
    nonce = Column(String, primary_key=True)
    target_url = Column(Text, nullable=False)
    purpose = Column(String, nullable=False)  # "external" | "internal"
    created_at = Column(DateTime(timezone=True), default=utcnow)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
