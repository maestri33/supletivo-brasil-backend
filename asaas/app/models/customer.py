"""Model SQLAlchemy: `asaas.customer` (pagadores cadastrados no Asaas)."""

from uuid import uuid4

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from ..db import Base, utcnow


class Customer(Base):
    """Pagadores cadastrados no Asaas (find-or-create).

    Necessario para criar cobrancas (Payment kind=charge) — Asaas /payments exige
    customer_id. Guardamos o mapeamento external_id (fornecido pelo cliente da API)
    -> asaas_id para nao duplicar customers no Asaas a cada cobranca.
    """

    __tablename__ = "customer"
    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    external_id = Column(String, unique=True, index=True, nullable=False)
    asaas_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    cpf_cnpj = Column(String, index=True, nullable=False)
    email = Column(String, nullable=True)
    mobile_phone = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
