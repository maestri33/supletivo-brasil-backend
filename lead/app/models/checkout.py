"""Model Checkout — estado de pagamento de um lead."""

from datetime import date
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class Checkout(Base, TimestampMixin):
    __tablename__ = "checkouts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "auth.users.external_id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="checkouts_external_id_fkey",
        ),
        unique=True,
        index=True,
        nullable=False,
    )

    # Cartao (infinitepay)
    checkout_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    receipt_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    invoice_slug: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    transaction_nsu: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    capture_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    installments: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Multi-provider (migration 0002)
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # PIX (asaas)
    qrcode_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    qrcode_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    is_paid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<Checkout {self.external_id} method={self.payment_method} paid={self.is_paid}>"
