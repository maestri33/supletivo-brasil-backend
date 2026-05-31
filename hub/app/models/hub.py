"""Hub (polo) — entidade raiz do serviço (SQLAlchemy 2).

Registro fino: guarda só o essencial do polo (nome, marca, endereço,
coordenador). Os papéis (promotores, alunos) pertencem aos seus próprios
serviços e referenciam o polo por `hub_external_id` (= este `id`).

Sem FK cross-schema: `address_external_id` e `coordinator_external_id` são
UUID puro, nullable (address já existe; coordinator ainda não).
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Hub(Base):
    __tablename__ = "hub"

    # Marcas conhecidas hoje (a validação fica no schema Pydantic, num próximo milestone).
    BRAND_ESTACIO = "estacio"
    BRAND_WYDEN = "wyden"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    brand: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    address_external_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    coordinator_external_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
