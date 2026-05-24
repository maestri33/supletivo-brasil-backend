"""Model SQLAlchemy: `asaas.payment` (PIX outbound e cobrancas inbound)."""

from uuid import uuid4

from sqlalchemy import Column, Date, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from ..db import Base, utcnow


class Payment(Base):
    """Pagamentos PIX — outbound (kind=pixkey|qrcode) e inbound (kind=charge).

    kind=pixkey   -> transferencia para chave PIX cadastrada (outbound)
    kind=qrcode   -> pagamento de BR Code copia-e-cola (outbound)
    kind=charge   -> cobranca PIX recebida via Asaas /payments (inbound)

    Status machines:
      outbound: SCHEDULED -> QUEUED -> SUBMITTING -> SUBMITTED -> PAID
                (ramo AWAITING_BALANCE entre QUEUED e SUBMITTED; falha -> FAILED|CANCELLED)
      charge:   PENDING -> PAID | EXPIRED | CANCELLED | REFUNDED
    """

    __tablename__ = "payment"
    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
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
    # NULL = imediato (so para outbound)
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, index=True)
    # outbound: SCHEDULED | QUEUED | SUBMITTING | SUBMITTED | AWAITING_BALANCE
    #           | PAID | FAILED | CANCELLED | NEEDS_RECONCILE
    # charge:   PENDING | PAID | EXPIRED | CANCELLED | REFUNDED
    asaas_id = Column(String, nullable=True, index=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
