"""initial notify schema

Tabelas no schema notify:
- notify.contacts (FK external_id -> auth.users.external_id, RESTRICT)
- notify.messages (FK contact_id -> notify.contacts.id, CASCADE)
- notify.logs (FK message_id -> notify.messages.id, CASCADE)

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


SCHEMA = "notify"


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="contacts_pkey"),
        sa.UniqueConstraint("external_id", name="contacts_external_id_key"),
        sa.UniqueConstraint("phone", name="contacts_phone_key"),
        sa.UniqueConstraint("email", name="contacts_email_key"),
        sa.ForeignKeyConstraint(
            ["external_id"], ["auth.users.external_id"],
            name="contacts_external_id_fkey",
            onupdate="CASCADE", ondelete="RESTRICT",
        ),
        schema=SCHEMA,
    )
    op.create_index("contacts_external_id_idx", "contacts", ["external_id"], schema=SCHEMA)
    op.create_index("contacts_phone_idx", "contacts", ["phone"], schema=SCHEMA)
    op.create_index("contacts_email_idx", "contacts", ["email"], schema=SCHEMA)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("whatsapp_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("email_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("email_subject", sa.String(length=255), nullable=True),
        sa.Column("tts_audio_url", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="messages_pkey"),
        sa.ForeignKeyConstraint(
            ["contact_id"], [f"{SCHEMA}.contacts.id"],
            name="messages_contact_id_fkey", ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index("messages_contact_id_idx", "messages", ["contact_id"], schema=SCHEMA)

    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="logs_pkey"),
        sa.ForeignKeyConstraint(
            ["message_id"], [f"{SCHEMA}.messages.id"],
            name="logs_message_id_fkey", ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index("logs_message_id_idx", "logs", ["message_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("logs", schema=SCHEMA)
    op.drop_table("messages", schema=SCHEMA)
    op.drop_table("contacts", schema=SCHEMA)
