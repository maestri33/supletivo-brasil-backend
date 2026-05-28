"""initial candidate schema

Tabela `candidates` no schema `candidate`.

PK = UUID (gerada na app, default uuid4). `external_id` e' o UUID do usuario
emitido pelo auth — referencia logica, sem FK cross-schema (mesma escolha do
asaas). Datas sao timestamptz. `status` e' o estado do funil (String).

Revision ID: 0001
Revises:
Create Date: 2026-05-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "candidate"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("hub_external_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="candidates_pkey"),
        sa.UniqueConstraint("external_id", name="candidates_external_id_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "candidates_external_id_idx", "candidates", ["external_id"], unique=True, schema=SCHEMA
    )
    op.create_index("candidates_status_idx", "candidates", ["status"], schema=SCHEMA)
    op.create_index(
        "candidates_hub_external_id_idx", "candidates", ["hub_external_id"], schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_table("candidates", schema=SCHEMA)
