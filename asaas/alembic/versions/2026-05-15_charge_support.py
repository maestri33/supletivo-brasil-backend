"""charge support: customer table + payment columns

Adiciona suporte a cobrancas PIX recebidas (kind=charge):
- Nova tabela `customer` (mapping external_id local -> Asaas customer)
- Novas colunas em `payment`: customer_external_id, pix_qr_image, due_date

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "asaas"


def upgrade() -> None:
    op.create_table(
        "customer",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("asaas_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("cpf_cnpj", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("mobile_phone", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("asaas_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_customer_external_id", "customer", ["external_id"], schema=SCHEMA)
    op.create_index("ix_customer_asaas_id", "customer", ["asaas_id"], schema=SCHEMA)
    op.create_index("ix_customer_cpf_cnpj", "customer", ["cpf_cnpj"], schema=SCHEMA)

    op.add_column(
        "payment",
        sa.Column("customer_external_id", sa.String(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "payment",
        sa.Column("pix_qr_image", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "payment",
        sa.Column("due_date", sa.Date(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_payment_customer_external_id",
        "payment",
        ["customer_external_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_payment_customer_external_id", table_name="payment", schema=SCHEMA)
    op.drop_column("payment", "due_date", schema=SCHEMA)
    op.drop_column("payment", "pix_qr_image", schema=SCHEMA)
    op.drop_column("payment", "customer_external_id", schema=SCHEMA)

    op.drop_index("ix_customer_cpf_cnpj", table_name="customer", schema=SCHEMA)
    op.drop_index("ix_customer_asaas_id", table_name="customer", schema=SCHEMA)
    op.drop_index("ix_customer_external_id", table_name="customer", schema=SCHEMA)
    op.drop_table("customer", schema=SCHEMA)
