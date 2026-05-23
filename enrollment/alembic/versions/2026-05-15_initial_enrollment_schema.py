"""initial enrollment schema

Tabela:
- enrollment.enrollment_events (FK external_id -> auth.users.external_id)

Stub auditivo: persiste cada webhook recebido do lead em `lead.completed`.

Revision ID: 0001
Revises:
Create Date: 2026-05-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "enrollment"


def upgrade() -> None:
    op.create_table(
        "enrollment_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("promoter_external_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="enrollment_events_pkey"),
        sa.ForeignKeyConstraint(
            ["external_id"], ["auth.users.external_id"],
            name="enrollment_events_external_id_fkey",
            onupdate="CASCADE", ondelete="RESTRICT",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "enrollment_events_external_id_idx", "enrollment_events",
        ["external_id"], schema=SCHEMA,
    )
    op.create_index(
        "enrollment_events_event_idx", "enrollment_events", ["event"], schema=SCHEMA,
    )
    op.create_index(
        "enrollment_events_promoter_external_id_idx", "enrollment_events",
        ["promoter_external_id"], schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("enrollment_events", schema=SCHEMA)
