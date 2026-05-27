"""Model Document — agregado de documentos de um usuario.

Referencias aos sub-documentos (rg, cnh, etc.) sao por UUID sem FK cross-schema.
O schema `documents` e dono das tabelas filhas.
"""

from uuid import uuid4

from sqlalchemy import String, Date
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")

# Tipos de certidao do registro civil brasileiro — termos consagrados; valor
# em pt-br por corresponder ao dado de mundo real (§15: identificador EN, dado pode ser pt-br).
CERTIFICATE_KINDS = {"nascimento", "casamento", "obito"}


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True, default=lambda: str(uuid4()))
    external_id: Mapped[str] = mapped_column(
        UUIDStr,
        unique=True,
        index=True,
        nullable=False,
        comment="UUID do usuario emitido pelo auth — referencia logica (sem FK)",
    )

    rg_id: Mapped[str | None] = mapped_column(UUIDStr, nullable=True)
    cnh_id: Mapped[str | None] = mapped_column(UUIDStr, nullable=True)
    work_card_id: Mapped[str | None] = mapped_column(UUIDStr, nullable=True)
    passport_id: Mapped[str | None] = mapped_column(UUIDStr, nullable=True)

    certificate_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    certificate_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    certificate_registry_office: Mapped[str | None] = mapped_column(String(100), nullable=True)
    certificate_book: Mapped[str | None] = mapped_column(String(20), nullable=True)
    certificate_page: Mapped[str | None] = mapped_column(String(20), nullable=True)
    certificate_entry: Mapped[str | None] = mapped_column(String(20), nullable=True)
    certificate_issue_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    certificate_photo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    military_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    military_series: Mapped[str | None] = mapped_column(String(20), nullable=True)
    military_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    military_ra: Mapped[str | None] = mapped_column(String(20), nullable=True)
    military_photo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    proof_of_residence_photo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    photo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<Document {self.external_id}>"
