"""initial asaas schema

Tabelas no schema asaas: config, url_verify_nonce, webhook_event, pix_key,
customer, payment.

Sem FK cross-schema — `external_id` aqui e fornecido pelo usuario (nao e
necessariamente o external_id do auth).

PK = UUID (gerada na app, default uuid4) em webhook_event/pix_key/customer/payment;
config e url_verify_nonce mantem PK String (key/nonce). Datas sao timestamptz e o
webhook_event guarda source_ip/user_agent da origem (§5).

As antigas revisions 0002 (charge_support) e 0003 (timestamptz) foram fundidas aqui.

Revision ID: 0001
Revises:
Create Date: 2026-05-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "asaas"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "config",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("key"),
        schema=SCHEMA,
    )

    op.create_table(
        "url_verify_nonce",
        sa.Column("nonce", sa.String(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("nonce"),
        schema=SCHEMA,
    )

    op.create_table(
        "webhook_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event", sa.String(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("forwarded_ok", sa.Boolean(), nullable=True),
        sa.Column("forwarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("ix_webhook_event_received_at", "webhook_event", ["received_at"], schema=SCHEMA)
    op.create_index("ix_webhook_event_event", "webhook_event", ["event"], schema=SCHEMA)

    op.create_table(
        "pix_key",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=True),
        sa.Column("key_type", sa.String(), nullable=True),
        sa.Column("holder_document", sa.String(), nullable=True),
        sa.Column("holder_name", sa.String(), nullable=True),
        sa.Column("bank_name", sa.String(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_dict", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("key"),
        schema=SCHEMA,
    )
    op.create_index("ix_pix_key_external_id", "pix_key", ["external_id"], schema=SCHEMA)
    op.create_index("ix_pix_key_key", "pix_key", ["key"], schema=SCHEMA)
    op.create_index("ix_pix_key_holder_document", "pix_key", ["holder_document"], schema=SCHEMA)

    op.create_table(
        "customer",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("asaas_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("cpf_cnpj", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("mobile_phone", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("asaas_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_customer_external_id", "customer", ["external_id"], schema=SCHEMA)
    op.create_index("ix_customer_asaas_id", "customer", ["asaas_id"], schema=SCHEMA)
    op.create_index("ix_customer_cpf_cnpj", "customer", ["cpf_cnpj"], schema=SCHEMA)

    op.create_table(
        "payment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("pixkey_external_id", sa.String(), nullable=True),
        sa.Column("qrcode_payload", sa.Text(), nullable=True),
        sa.Column("customer_external_id", sa.String(), nullable=True),
        sa.Column("pix_qr_image", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("asaas_id", sa.String(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_payment_payment_id", "payment", ["payment_id"], schema=SCHEMA)
    op.create_index("ix_payment_kind", "payment", ["kind"], schema=SCHEMA)
    op.create_index(
        "ix_payment_pixkey_external_id", "payment", ["pixkey_external_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_payment_customer_external_id", "payment", ["customer_external_id"], schema=SCHEMA
    )
    op.create_index("ix_payment_status", "payment", ["status"], schema=SCHEMA)
    op.create_index("ix_payment_asaas_id", "payment", ["asaas_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("payment", schema=SCHEMA)
    op.drop_table("customer", schema=SCHEMA)
    op.drop_table("pix_key", schema=SCHEMA)
    op.drop_table("webhook_event", schema=SCHEMA)
    op.drop_table("url_verify_nonce", schema=SCHEMA)
    op.drop_table("config", schema=SCHEMA)
