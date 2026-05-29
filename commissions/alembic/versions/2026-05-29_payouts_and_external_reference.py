"""create payouts table + commissions.external_reference

Reescrita do payout (desenho do dono): 1 pagamento por beneficiario por semana,
idempotente por external_reference, empurrado pro asaas que detem a fila pesada.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "commissions"


def upgrade() -> None:
    # Enum do status do payout
    op.execute(
        f"CREATE TYPE {SCHEMA}.payout_status AS ENUM "
        "('queued', 'submitted', 'awaiting_balance', 'paid', 'failed', 'cancelled')"
    )

    # Tabela payouts — 1 solicitacao de pagamento por beneficiario por semana
    op.create_table(
        "payouts",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column(
            "external_reference", sa.String(128), nullable=False,
            comment="Chave de idempotencia; enviada ao asaas como payment_id",
        ),
        sa.Column(
            "recipient_external_id", PG_UUID(as_uuid=True), nullable=False,
            comment="UUID do beneficiario (= external_id da pixkey no asaas). Sem FK cross-schema (§4)",
        ),
        sa.Column(
            "recipient_role", sa.String(32), nullable=False,
            comment="promoter | coordinator",
        ),
        sa.Column(
            "amount_cents", sa.Integer(), nullable=False,
            comment="Soma comissoes+bonus do beneficiario no lote, em centavos",
        ),
        sa.Column(
            "week_of", sa.String(10), nullable=False,
            comment="Segunda-feira ISO da semana de referencia",
        ),
        sa.Column(
            "payment_batch_id", sa.BigInteger(), nullable=True,
            comment="Lote semanal que originou este payout",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "queued", "submitted", "awaiting_balance", "paid", "failed", "cancelled",
                name="payout_status", schema=SCHEMA, create_type=False,
            ),
            nullable=False, server_default=sa.text("'queued'"),
        ),
        sa.Column("asaas_id", sa.String(), nullable=True,
                  comment="UUID da transferencia/transacao no asaas"),
        sa.Column("asaas_status", sa.String(32), nullable=True,
                  comment="Ultimo status recebido do asaas, verbatim"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("7")),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True,
                  comment="Quando o worker tenta empurrar/reconciliar de novo (NULL = pronto agora)"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_payouts"),
        sa.UniqueConstraint("external_reference", name="uq_payouts_external_reference"),
        sa.ForeignKeyConstraint(
            ["payment_batch_id"], [f"{SCHEMA}.payment_batches.id"],
            name="fk_payouts_payment_batch_id",
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_payouts_external_reference", "payouts",
                    ["external_reference"], schema=SCHEMA)
    op.create_index("ix_payouts_recipient_external_id", "payouts",
                    ["recipient_external_id"], schema=SCHEMA)
    op.create_index("ix_payouts_week_of", "payouts", ["week_of"], schema=SCHEMA)
    op.create_index("ix_payouts_status", "payouts", ["status"], schema=SCHEMA)
    op.create_index("ix_payouts_payment_batch_id", "payouts",
                    ["payment_batch_id"], schema=SCHEMA)
    op.create_index("ix_payouts_next_attempt_at", "payouts",
                    ["next_attempt_at"], schema=SCHEMA)

    # Carimbo de idempotencia em cada comissao/bonus
    op.add_column(
        "commissions",
        sa.Column("external_reference", sa.String(128), nullable=True,
                  comment="Referencia do payout que liquida esta comissao"),
        schema=SCHEMA,
    )
    op.create_index("ix_commissions_external_reference", "commissions",
                    ["external_reference"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_commissions_external_reference", "commissions", schema=SCHEMA)
    op.drop_column("commissions", "external_reference", schema=SCHEMA)
    op.drop_table("payouts", schema=SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.payout_status")
