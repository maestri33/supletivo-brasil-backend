"""widen url columns to TEXT

InfinitePay devolve checkout_url com token `lenc` de >500 chars (~700+).
varchar(500) trunca. Movemos as colunas de URL para TEXT.

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


SCHEMA = "infinitepay"


def upgrade() -> None:
    with op.batch_alter_table("checkouts", schema=SCHEMA) as batch_op:
        batch_op.alter_column("checkout_url", type_=sa.Text(), existing_nullable=False)
        batch_op.alter_column("receipt_url", type_=sa.Text(), existing_nullable=True)

    with op.batch_alter_table("outbound_jobs", schema=SCHEMA) as batch_op:
        batch_op.alter_column("url", type_=sa.Text(), existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("checkouts", schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "checkout_url", type_=sa.String(length=500), existing_nullable=False
        )
        batch_op.alter_column(
            "receipt_url", type_=sa.String(length=500), existing_nullable=True
        )

    with op.batch_alter_table("outbound_jobs", schema=SCHEMA) as batch_op:
        batch_op.alter_column("url", type_=sa.String(length=500), existing_nullable=False)
