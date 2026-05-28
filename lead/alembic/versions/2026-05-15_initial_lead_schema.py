"""initial lead schema

Cria as tabelas do schema `lead` no Postgres central:
- lead.leads (external_id UUID opaco, sem FK cross-schema §4)
- lead.checkouts
- lead.messages

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


SCHEMA = "lead"


def upgrade() -> None:
    # Enum lead_status (no schema lead)
    lead_status = postgresql.ENUM(
        "captured",
        "waiting",
        "checkout",
        "completed",
        name="lead_status",
        schema=SCHEMA,
        create_type=True,
    )
    lead_status.create(op.get_bind(), checkfirst=True)

    # leads
    op.create_table(
        "leads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "captured",
                "waiting",
                "checkout",
                "completed",
                name="lead_status",
                schema=SCHEMA,
                create_type=False,
            ),
            nullable=False,
            server_default="captured",
        ),
        sa.Column("promoter_external_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="leads_pkey"),
        sa.UniqueConstraint("external_id", name="leads_external_id_key"),
        schema=SCHEMA,
    )
    op.create_index("leads_status_idx", "leads", ["status"], schema=SCHEMA)
    op.create_index(
        "leads_promoter_external_id_idx",
        "leads",
        ["promoter_external_id"],
        schema=SCHEMA,
    )

    # checkouts
    op.create_table(
        "checkouts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checkout_url", sa.String(length=1024), nullable=True),
        sa.Column("receipt_url", sa.String(length=1024), nullable=True),
        sa.Column("invoice_slug", sa.String(length=255), nullable=True),
        sa.Column("transaction_nsu", sa.String(length=255), nullable=True),
        sa.Column("capture_method", sa.String(length=50), nullable=True),
        sa.Column("installments", sa.SmallInteger(), nullable=True),
        sa.Column(
            "is_paid",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="checkouts_pkey"),
        sa.UniqueConstraint("external_id", name="checkouts_external_id_key"),
        schema=SCHEMA,
    )
    op.create_index("checkouts_invoice_slug_idx", "checkouts", ["invoice_slug"], schema=SCHEMA)
    op.create_index(
        "checkouts_transaction_nsu_idx",
        "checkouts",
        ["transaction_nsu"],
        schema=SCHEMA,
    )
    op.create_index("checkouts_is_paid_idx", "checkouts", ["is_paid"], schema=SCHEMA)

    # messages
    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "direction",
            sa.String(length=10),
            server_default="out",
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=20), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("event", sa.String(length=50), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="messages_pkey"),
        schema=SCHEMA,
    )
    op.create_index("messages_message_id_idx", "messages", ["message_id"], schema=SCHEMA)
    op.create_index("messages_external_id_idx", "messages", ["external_id"], schema=SCHEMA)
    op.create_index("messages_status_idx", "messages", ["status"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("messages", schema=SCHEMA)
    op.drop_table("checkouts", schema=SCHEMA)
    op.drop_table("leads", schema=SCHEMA)
    postgresql.ENUM(name="lead_status", schema=SCHEMA).drop(op.get_bind(), checkfirst=True)
