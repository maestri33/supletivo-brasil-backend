"""create commissions and payment_batches tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "commissions"


def upgrade() -> None:
    # Create enum types
    op.execute(
        f"CREATE TYPE {SCHEMA}.commission_status AS ENUM ('pending', 'processed', 'paid', 'failed', 'cancelled')"
    )
    op.execute(
        f"CREATE TYPE {SCHEMA}.payment_batch_status AS ENUM ('pending', 'processing', 'completed', 'failed')"
    )

    # payment_batches first (commissions FK references it)
    op.create_table(
        "payment_batches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "week_of", sa.String(10), nullable=False, index=True,
            comment="Data ISO da segunda-feira da semana de referencia (ex: 2026-05-25)",
        ),
        sa.Column(
            "total_cents", sa.Integer(), nullable=False, server_default=sa.text("0"),
            comment="Valor total do lote em centavos (comissoes + bonus)",
        ),
        sa.Column(
            "bonus_cents", sa.Integer(), nullable=False, server_default=sa.text("0"),
            comment="Valor total de bonus incluso no lote em centavos",
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed",
                    name="payment_batch_status", schema=SCHEMA, create_type=False),
            nullable=False, server_default=sa.text("'pending'"), index=True,
        ),
        sa.Column("pix_transaction_id", sa.String(), nullable=True,
                  comment="ID da transacao PIX no Asaas"),
        sa.Column("asaas_transfer_id", sa.String(), nullable=True,
                  comment="ID da transferencia no Asaas"),
        sa.Column("last_error", sa.Text(), nullable=True,
                  comment="Ultimo erro registrado na tentativa de pagamento"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_payment_batches"),
        schema=SCHEMA,
    )
    op.create_index("ix_payment_batches_week_of", "payment_batches", ["week_of"], schema=SCHEMA)
    op.create_index("ix_payment_batches_status", "payment_batches", ["status"], schema=SCHEMA)

    # commissions table
    op.create_table(
        "commissions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("recipient_external_id", PG_UUID(as_uuid=True), nullable=False,
                  comment="UUID do usuario que recebe a comissao"),
        sa.Column("recipient_role", sa.String(32), nullable=False, index=True,
                  comment="Funcao do receptor: promoter, coordinator"),
        sa.Column("source_type", sa.String(32), nullable=False, index=True,
                  comment="Tipo de entidade que originou: lead, student_completion"),
        sa.Column("source_external_id", PG_UUID(as_uuid=True), nullable=False, index=True,
                  comment="UUID externo da entidade de origem"),
        sa.Column("amount_cents", sa.Integer(), nullable=False,
                  comment="Valor da comissao em centavos"),
        sa.Column(
            "status",
            sa.Enum("pending", "processed", "paid", "failed", "cancelled",
                    name="commission_status", schema=SCHEMA, create_type=False),
            nullable=False, server_default=sa.text("'pending'"), index=True,
        ),
        sa.Column("payment_batch_id", sa.BigInteger(), nullable=True,
                  comment="Lote de pagamento ao qual esta comissao pertence"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["recipient_external_id"], ["auth.users.external_id"],
            name="fk_commissions_recipient_external_id",
            ondelete="RESTRICT", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payment_batch_id"], [f"{SCHEMA}.payment_batches.id"],
            name="fk_commissions_payment_batch_id",
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_commissions"),
        schema=SCHEMA,
    )
    op.create_index("ix_commissions_recipient_external_id", "commissions",
                    ["recipient_external_id"], schema=SCHEMA)
    op.create_index("ix_commissions_recipient_role", "commissions",
                    ["recipient_role"], schema=SCHEMA)
    op.create_index("ix_commissions_source_type", "commissions",
                    ["source_type"], schema=SCHEMA)
    op.create_index("ix_commissions_source_external_id", "commissions",
                    ["source_external_id"], schema=SCHEMA)
    op.create_index("ix_commissions_status", "commissions",
                    ["status"], schema=SCHEMA)
    op.create_index("ix_commissions_payment_batch_id", "commissions",
                    ["payment_batch_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("commissions", schema=SCHEMA)
    op.drop_table("payment_batches", schema=SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.commission_status")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.payment_batch_status")
