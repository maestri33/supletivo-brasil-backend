"""Model Candidate — aspirante a promotor, conduzido pelo funil de cadastro.

Estado local minimo: o servico orquestra o funil; perfil, endereco, documentos
e chave pix vivem nos servicos donos (profiles, address, documents, asaas).
"""

import enum
from uuid import uuid4

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

# UUID nativo no Postgres; em sqlite (testes) vira String(36) com afinidade TEXT
# — sem isso o sqlite da afinidade NUMERIC ao tipo UUID e converte uuids
# all-zeros ("0000...") em inteiro 0, quebrando a leitura.
UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


class CandidateStatus(enum.StrEnum):
    """Etapas sequenciais do funil (CONVENTION: espelha a logica do lead)."""

    CAPTURED = "captured"
    PERSONAL = "personal"
    EDUCATION = "education"
    BIRTH = "birth"
    ADDRESS = "address"
    DOCUMENTS = "documents"
    PIXKEY = "pixkey"
    SELFIE = "selfie"
    COMPLETED = "completed"


# Ordem do funil — usada para transicoes e validacao de avanco.
STATUS_ORDER: tuple[CandidateStatus, ...] = (
    CandidateStatus.CAPTURED,
    CandidateStatus.PERSONAL,
    CandidateStatus.EDUCATION,
    CandidateStatus.BIRTH,
    CandidateStatus.ADDRESS,
    CandidateStatus.DOCUMENTS,
    CandidateStatus.PIXKEY,
    CandidateStatus.SELFIE,
    CandidateStatus.COMPLETED,
)


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidates"

    # as_uuid=False: armazena/retorna str — o servico trafega external_id como
    # string (URLs, JSON, JWT); evita conversoes e casa com o driver no sqlite/PG.
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

    status: Mapped[str] = mapped_column(
        String(20),
        default=CandidateStatus.CAPTURED.value,
        nullable=False,
        index=True,
        comment="Etapa atual do funil",
    )

    hub_external_id: Mapped[str | None] = mapped_column(
        UUIDStr,
        nullable=True,
        index=True,
        comment="UUID do hub ao qual o candidato pertence",
    )

    def __repr__(self) -> str:
        return f"<Candidate {self.external_id} status={self.status}>"
