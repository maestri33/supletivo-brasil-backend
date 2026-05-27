"""Model Document — agregado de documentos de um usuario.

Referencias aos sub-documentos (rg, cnh, etc.) sao por UUID sem FK cross-schema
— mesma escolha do asaas/candidate. O schema `documents` e dono das tabelas filhas.
"""

from uuid import uuid4

from sqlalchemy import String, Date
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")

CERTIDAO_TIPOS = {"nascimento", "casamento", "obito"}


class Document(Base, TimestampMixin):
    __tablename__ = "documentos"

    id: Mapped[str] = mapped_column(
        UUIDStr,
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    external_id: Mapped[str] = mapped_column(
        UUIDStr,
        unique=True,
        index=True,
        nullable=False,
        comment="UUID do usuario emitido pelo auth — referencia logica (sem FK)",
    )

    # FK pointers (UUID — logical references, no cross-schema FK)
    rg_id: Mapped[str | None] = mapped_column(UUIDStr, nullable=True)
    cnh_id: Mapped[str | None] = mapped_column(UUIDStr, nullable=True)
    carteira_trabalho_id: Mapped[str | None] = mapped_column(UUIDStr, nullable=True)
    passaporte_id: Mapped[str | None] = mapped_column(UUIDStr, nullable=True)

    # Certidao (nascimento / casamento / obito)
    certidao_tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    certidao_numero: Mapped[str | None] = mapped_column(String(50), nullable=True)
    certidao_cartorio: Mapped[str | None] = mapped_column(String(100), nullable=True)
    certidao_livro: Mapped[str | None] = mapped_column(String(20), nullable=True)
    certidao_folha: Mapped[str | None] = mapped_column(String(20), nullable=True)
    certidao_termo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    certidao_data_emissao: Mapped[str | None] = mapped_column(Date, nullable=True)
    certidao_foto: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Reservista
    reservista_numero: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reservista_serie: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reservista_categoria: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reservista_ra: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reservista_foto: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Comprovante de residencia
    comprovante_residencia_foto: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # Foto geral (opcional)
    foto: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<Document {self.external_id}>"
