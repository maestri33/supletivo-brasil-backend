"""Address — entidade raiz (SQLAlchemy 2)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Address(Base):
    __tablename__ = "addresses"

    KIND_HOME = "home"
    KIND_BILLING = "billing"
    KIND_SHIPPING = "shipping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "auth.users.external_id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="addresses_external_id_fkey",
        ),
        index=True,
        nullable=False,
    )

    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    zipcode: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    street: Mapped[str] = mapped_column(String(200), nullable=False)
    number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    complement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    neighborhood: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, server_default="BR")

    # Geo — feature do LOCAL preservada (nullable, não faz parte do contrato base da produção).
    lat: Mapped[str | None] = mapped_column(String(30), nullable=True)
    lng: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
