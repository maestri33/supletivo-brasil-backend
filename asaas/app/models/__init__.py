"""SQLAlchemy ORM models."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text

from ..db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ConfigKV(Base):
    """Single-row key/value config. One row per key."""

    __tablename__ = "config"
    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class UrlVerifyNonce(Base):
    """Nonces issued during external-URL validation."""

    __tablename__ = "url_verify_nonce"
    nonce = Column(String, primary_key=True)
    target_url = Column(Text, nullable=False)
    purpose = Column(String, nullable=False)  # "external" | "internal"
    created_at = Column(DateTime, default=_utcnow)
    consumed_at = Column(DateTime, nullable=True)


class WebhookEvent(Base):
    """Raw webhook payloads received from Asaas."""

    __tablename__ = "webhook_event"
    id = Column(Integer, primary_key=True, autoincrement=True)
    received_at = Column(DateTime, default=_utcnow, index=True)
    event = Column(String, index=True)
    payload = Column(Text)
    forwarded_ok = Column(Boolean, default=False)
    forwarded_at = Column(DateTime, nullable=True)


class PixKey(Base):
    """PIX keys we registered in our own namespace after DICT validation.

    Ownership: external_id eh o identificador fornecido pelo usuario (nosso cliente
    vai referenciar por ele em payment). key eh a chave PIX propriamente dita.
    """

    __tablename__ = "pix_key"
    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String, unique=True, index=True, nullable=False)
    key = Column(String, unique=True, index=True)
    key_type = Column(String)  # CPF | CNPJ | EMAIL | PHONE | EVP
    holder_document = Column(String, index=True)  # CPF (11) ou CNPJ (14) do titular
    holder_name = Column(String)
    bank_name = Column(String)
    validated_at = Column(DateTime, default=_utcnow)
    raw_dict = Column(Text)


class Customer(Base):
    """Pagadores cadastrados no Asaas (find-or-create).

    Necessario para criar cobrancas (Payment kind=charge) — Asaas /payments exige
    customer_id. Guardamos o mapeamento external_id (fornecido pelo cliente da API)
    → asaas_id para nao duplicar customers no Asaas a cada cobranca.
    """

    __tablename__ = "customer"
    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String, unique=True, index=True, nullable=False)
    asaas_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    cpf_cnpj = Column(String, index=True, nullable=False)
    email = Column(String, nullable=True)
    mobile_phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class Payment(Base):
    """Pagamentos PIX — outbound (kind=pixkey|qrcode) e inbound (kind=charge).

    kind=pixkey   → transferencia para chave PIX cadastrada (outbound)
    kind=qrcode   → pagamento de BR Code copia-e-cola (outbound)
    kind=charge   → cobranca PIX recebida via Asaas /payments (inbound)

    Status machines:
      outbound: SCHEDULED → QUEUED → SUBMITTING → SUBMITTED → PAID
                              ↘ AWAITING_BALANCE ↗            ↘ FAILED | CANCELLED
      charge:   PENDING → PAID | EXPIRED | CANCELLED | REFUNDED
    """

    __tablename__ = "payment"
    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(String, unique=True, index=True)  # user-provided ou uuid gerado
    kind = Column(String, index=True)  # "pixkey" | "qrcode" | "charge"

    # kind=pixkey
    pixkey_external_id = Column(String, index=True, nullable=True)  # ref para PixKey.external_id

    # kind=qrcode (outbound BR Code paid) e kind=charge (BR Code retornado pelo Asaas)
    qrcode_payload = Column(Text, nullable=True)

    # kind=charge
    customer_external_id = Column(
        String, index=True, nullable=True
    )  # ref para Customer.external_id
    pix_qr_image = Column(Text, nullable=True)  # PNG base64 do QR Code (kind=charge)
    due_date = Column(Date, nullable=True)  # vencimento da cobranca

    amount = Column(Float)
    description = Column(Text, nullable=True)
    scheduled_for = Column(DateTime, nullable=True)  # NULL = imediato (so para outbound)
    status = Column(String, index=True)
    # outbound: SCHEDULED | QUEUED | SUBMITTING | SUBMITTED | AWAITING_BALANCE
    #           | PAID | FAILED | CANCELLED
    # charge:   PENDING | PAID | EXPIRED | CANCELLED | REFUNDED
    asaas_id = Column(String, nullable=True, index=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
