"""initial promoter schema

Tabela `promoters` no schema `promoter`.

PK = UUID (gerada na app, default uuid4). `external_id` e' o UUID do usuario
emitido pelo auth — referencia logica, sem FK cross-schema (mesma escolha do
candidate/asaas) — e tambem e' o `ref` divulgado na captacao. Datas sao
timestamptz. `status` e' active/suspended (String).

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


SCHEMA = "promoter"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "promoters",
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
        sa.PrimaryKeyConstraint("id", name="promoters_pkey"),
        sa.UniqueConstraint("external_id", name="promoters_external_id_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "promoters_external_id_idx", "promoters", ["external_id"], unique=True, schema=SCHEMA
    )
    op.create_index("promoters_status_idx", "promoters", ["status"], schema=SCHEMA)
    op.create_index(
        "promoters_hub_external_id_idx", "promoters", ["hub_external_id"], schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_table("promoters", schema=SCHEMA)
