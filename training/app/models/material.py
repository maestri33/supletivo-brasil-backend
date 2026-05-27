"""Model Material — uma "materia" do treinamento.

Cada materia tem 1 texto, 1 questao e 1 resposta esperada (gabarito), mais,
opcionalmente, 1 video e 1 foto. Os binarios ficam em MEDIA_DIR; aqui guardamos
so' o caminho relativo (`video_path`/`photo_path`), nulo ate o upload.
"""

from uuid import uuid4

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

# UUID nativo no Postgres; em sqlite (testes) vira String(36) com afinidade TEXT
# — mesma escolha do candidate, para o sqlite nao converter UUID em NUMERIC.
UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


class Material(Base, TimestampMixin):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(
        UUIDStr,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="Nome da materia")
    text_content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Conteudo textual da materia"
    )
    question: Mapped[str] = mapped_column(Text, nullable=False, comment="Questao unica da materia")
    expected_answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Resposta esperada (gabarito) — base da correcao por IA no M2",
    )

    video_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Caminho relativo do video em MEDIA_DIR; null ate o upload",
    )
    photo_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Caminho relativo da foto em MEDIA_DIR; null ate o upload",
    )

    def __repr__(self) -> str:
        return f"<Material {self.id} {self.title!r}>"
