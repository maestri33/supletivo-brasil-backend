"""outbound_jobs: fila de saida com retry pra notify_internal

Tabela `asaas.outbound_jobs` espelha infinitepay.outbound_jobs (mesmo pattern
do worker em app/workers/outbound_queue.py). Sem FK cross-schema (§4 da
CONVENTION). Indices em (delivered_at, next_attempt_at) e external_id.

Motivo (race PENDING-before-checkout, 28/05): asaas mandava notify direto via
httpx.post; se a URL caia ou o lead nao tinha commitado o checkout, evento
sumia. Com a fila, enqueue fica atomico com o estado e o worker reentrega.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "asaas"


def upgrade() -> None:
    op.create_table(
        "outbound_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "outbound_jobs_external_id_idx",
        "outbound_jobs",
        ["external_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "outbound_jobs_next_attempt_at_idx",
        "outbound_jobs",
        ["next_attempt_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("outbound_jobs_next_attempt_at_idx", table_name="outbound_jobs", schema=SCHEMA)
    op.drop_index("outbound_jobs_external_id_idx", table_name="outbound_jobs", schema=SCHEMA)
    op.drop_table("outbound_jobs", schema=SCHEMA)
