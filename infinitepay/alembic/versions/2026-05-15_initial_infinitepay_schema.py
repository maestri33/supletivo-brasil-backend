"""initial infinitepay schema

Tabelas:
- infinitepay.config
- infinitepay.checkouts (FK external_id -> auth.users RESTRICT)
- infinitepay.webhook_logs (FK external_id -> auth.users SET NULL)
- infinitepay.outbound_jobs (FK external_id -> auth.users SET NULL)

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


SCHEMA = "infinitepay"


def upgrade() -> None:
    op.create_table(
        "config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("handle", sa.String(length=128), nullable=True),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("redirect_url", sa.String(length=500), nullable=True),
        sa.Column("backend_webhook", sa.String(length=500), nullable=True),
        sa.Column("public_api_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )

    op.create_table(
        "checkouts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checkout_url", sa.String(length=500), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False),
        sa.Column("receipt_url", sa.String(length=500), nullable=True),
        sa.Column("installments", sa.Integer(), nullable=True),
        sa.Column("invoice_slug", sa.String(length=128), nullable=True),
        sa.Column("capture_method", sa.String(length=32), nullable=True),
        sa.Column("transaction_nsu", sa.String(length=128), nullable=True),
        sa.Column("request_payload", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("response_payload", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.ForeignKeyConstraint(
            ["external_id"], ["auth.users.external_id"],
            name="checkouts_external_id_fkey",
            onupdate="CASCADE", ondelete="RESTRICT",
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_checkouts_external_id", "checkouts", ["external_id"], schema=SCHEMA)

    op.create_table(
        "webhook_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("payload", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("response", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["external_id"], ["auth.users.external_id"],
            name="webhook_logs_external_id_fkey",
            onupdate="CASCADE", ondelete="SET NULL",
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_webhook_logs_external_id", "webhook_logs", ["external_id"], schema=SCHEMA)

    op.create_table(
        "outbound_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("payload", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["external_id"], ["auth.users.external_id"],
            name="outbound_jobs_external_id_fkey",
            onupdate="CASCADE", ondelete="SET NULL",
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_outbound_jobs_external_id", "outbound_jobs", ["external_id"], schema=SCHEMA)
    op.create_index("ix_outbound_jobs_next_attempt_at", "outbound_jobs", ["next_attempt_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("outbound_jobs", schema=SCHEMA)
    op.drop_table("webhook_logs", schema=SCHEMA)
    op.drop_table("checkouts", schema=SCHEMA)
    op.drop_table("config", schema=SCHEMA)
