"""initial hub schema

Schema `hub` com a tabela `hub` (polo): registro fino com nome/marca/endereço/
coordenador. PK = UUID (gerada na app, default uuid4). Refs cross-service
(`address_external_id`, `coordinator_external_id`) são UUID puro, nullable —
sem FK cross-schema. Datas em timestamptz.

Semeia 1 polo default (UUID fixo, idempotente via ON CONFLICT) — ver app/seed.py.

Revision ID: 0001
Revises:
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.seed import default_hub_insert_sql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "hub"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "hub",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("brand", sa.String(length=40), nullable=False),
        sa.Column("address_external_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("coordinator_external_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("hub_brand_idx", "hub", ["brand"], schema=SCHEMA)
    op.create_index("hub_address_external_id_idx", "hub", ["address_external_id"], schema=SCHEMA)
    op.create_index(
        "hub_coordinator_external_id_idx", "hub", ["coordinator_external_id"], schema=SCHEMA
    )

    # Seed do polo default (idempotente; mesma SQL exercida pelos testes).
    op.execute(default_hub_insert_sql(SCHEMA))


def downgrade() -> None:
    op.drop_table("hub", schema=SCHEMA)
