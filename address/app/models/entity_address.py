"""EntityAddress — vínculo polimórfico (feature do LOCAL, portada p/ SQLAlchemy 2).

Diferente de `addresses.addresses` (que pertence a `auth.users` via UUID e tem
NOT NULLs), aqui o "dono" é polimórfico — `(entity_type, external_id)` como
strings livres (user/hub/atendimento/parceiro...). Por isso o endereço fica numa
tabela própria (`entity_address_details`), totalmente nullable, evitando o
conflito com o contrato estrito da tabela `addresses`.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class EntityAddressDetail(Base):
    """Endereço genérico/avulso ligado a uma EntityAddress. Tudo nullable."""

    __tablename__ = "entity_address_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    street: Mapped[str | None] = mapped_column(String(200), nullable=True)
    number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    complement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    neighborhood: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    zipcode: Mapped[str | None] = mapped_column(String(8), nullable=True)
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


class EntityAddress(Base):
    __tablename__ = "entity_addresses"
    __table_args__ = (
        UniqueConstraint("entity_type", "external_id", name="entity_addresses_entity_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    proof_file: Mapped[str | None] = mapped_column(String(255), nullable=True)

    address_id: Mapped[int | None] = mapped_column(
        ForeignKey("entity_address_details.id", ondelete="SET NULL"),
        nullable=True,
    )
    address: Mapped[EntityAddressDetail | None] = relationship(lazy="selectin")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
