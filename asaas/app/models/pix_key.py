"""Model SQLAlchemy: `asaas.pix_key` (chaves PIX validadas no DICT)."""

from uuid import uuid4

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from ..db import Base, utcnow


class PixKey(Base):
    """PIX keys we registered in our own namespace after DICT validation.

    Ownership: external_id eh o identificador fornecido pelo usuario (nosso cliente
    vai referenciar por ele em payment). key eh a chave PIX propriamente dita.
    """

    __tablename__ = "pix_key"
    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    external_id = Column(String, unique=True, index=True, nullable=False)
    key = Column(String, unique=True, index=True)
    key_type = Column(String)  # CPF | CNPJ | EMAIL | PHONE | EVP
    holder_document = Column(String, index=True)  # CPF (11) ou CNPJ (14) do titular
    holder_name = Column(String)
    bank_name = Column(String)
    validated_at = Column(DateTime(timezone=True), default=utcnow)
    raw_dict = Column(Text)
