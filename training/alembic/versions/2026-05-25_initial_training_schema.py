"""initial training schema

Tabela `materials` no schema `training`.

PK = UUID (gerada na app, default uuid4). Uma materia tem 1 texto, 1 questao,
1 resposta esperada (gabarito) e, opcionalmente, 1 video e 1 foto cujos arquivos
ficam no proprio training (MEDIA_DIR) — aqui guardamos so' o caminho relativo.

Revision ID: 0001
Revises:
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "training"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=False),
        sa.Column("video_path", sa.String(length=500), nullable=True),
        sa.Column("photo_path", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="materials_pkey"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("materials", schema=SCHEMA)
