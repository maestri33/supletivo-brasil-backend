"""rate_limit table + metrics columns

Adiciona:
- Tabela `otp.rate_limit` (controle por external_id).
- Colunas `otp.otp_logs.attempts` (int, default 0).
- Colunas `otp.otp_logs.failure_reason` (string, nullable).

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "otp"


def upgrade() -> None:
    # ── colunas novas em otp.otp_logs ──
    op.add_column(
        "otp_logs",
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        schema=SCHEMA,
    )
    op.add_column(
        "otp_logs",
        sa.Column("failure_reason", sa.String(length=20), nullable=True),
        schema=SCHEMA,
    )

    # ── nova tabela otp.rate_limit ──
    op.create_table(
        "rate_limit",
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hourly_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hourly_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("external_id", name="rate_limit_pkey"),
        sa.ForeignKeyConstraint(
            ["external_id"], ["auth.users.external_id"],
            name="rate_limit_external_id_fkey",
            onupdate="CASCADE", ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("rate_limit", schema=SCHEMA)
    op.drop_column("otp_logs", "failure_reason", schema=SCHEMA)
    op.drop_column("otp_logs", "attempts", schema=SCHEMA)
