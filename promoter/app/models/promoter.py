"""Model Promoter — divulgador aprovado, dono de um link de captacao de leads.

Estado local minimo: o promoter eh criado quando o coordenador do polo aprova o
candidato (apos treinamento + entrevista). Perfil, endereco, chave pix vivem nos
servicos donos; leads e comissoes vivem em `lead`/`commissions`. Aqui guardamos
so' a identidade do promoter (external_id), o hub a que pertence e seu status.

O `external_id` eh tambem o `ref` divulgado na landing: `<landing>/ref=<external_id>`.
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


class PromoterStatus(enum.StrEnum):
    """Estado do promoter. Suspenso nao capta leads nem recebe comissao."""

    ACTIVE = "active"
    SUSPENDED = "suspended"


class Promoter(Base, TimestampMixin):
    __tablename__ = "promoters"

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
        comment="UUID do usuario emitido pelo auth — referencia logica (sem FK); tambem eh o ref",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=PromoterStatus.ACTIVE.value,
        nullable=False,
        index=True,
        comment="Estado do promoter (active/suspended)",
    )

    hub_external_id: Mapped[str | None] = mapped_column(
        UUIDStr,
        nullable=True,
        index=True,
        comment="UUID do hub (polo) ao qual o promoter pertence",
    )

    def __repr__(self) -> str:
        return f"<Promoter {self.external_id} status={self.status}>"
