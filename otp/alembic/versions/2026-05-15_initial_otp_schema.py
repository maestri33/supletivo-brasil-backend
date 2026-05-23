"""initial otp schema

Cria as tabelas do schema `otp`:
- otp.otp_logs (FK external_id -> auth.users.external_id)
- otp.pending_notify (FK external_id -> auth.users; FK otp_log_id -> otp.otp_logs)

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


SCHEMA = "otp"


def upgrade() -> None:
    op.create_table(
        "otp_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="generated", nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="otp_logs_pkey"),
        sa.ForeignKeyConstraint(
            ["external_id"], ["auth.users.external_id"],
            name="otp_logs_external_id_fkey",
            onupdate="CASCADE", ondelete="RESTRICT",
        ),
        schema=SCHEMA,
    )
    op.create_index("otp_logs_external_id_idx", "otp_logs", ["external_id"], schema=SCHEMA)

    op.create_table(
        "pending_notify",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("otp_log_id", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="1", nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pending_notify_pkey"),
        sa.ForeignKeyConstraint(
            ["external_id"], ["auth.users.external_id"],
            name="pending_notify_external_id_fkey",
            onupdate="CASCADE", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["otp_log_id"], [f"{SCHEMA}.otp_logs.id"],
            name="pending_notify_otp_log_id_fkey",
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index("pending_notify_external_id_idx", "pending_notify", ["external_id"], schema=SCHEMA)
    op.create_index("pending_notify_otp_log_id_idx", "pending_notify", ["otp_log_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("pending_notify", schema=SCHEMA)
    op.drop_table("otp_logs", schema=SCHEMA)
