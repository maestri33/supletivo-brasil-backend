"""initial fees schema

Tabelas:
- fees.fee          — taxa de matrícula por aluno (status derivado)
- fees.fee_payment  — os dois payouts PIX (upfront/scheduled) da taxa

Referências por valor (sem FK): `fee_payment.fee_id` -> `fee.id`,
`fee.student_external_id`/`coordinator_external_id` são UUIDs opacos.

Revision ID: 0001
Revises:
Create Date: 2026-05-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "fees"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "fee",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("student_external_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("coordinator_external_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="fee_pkey"),
        schema=SCHEMA,
    )
    op.create_index("fee_student_external_id_idx", "fee", ["student_external_id"], schema=SCHEMA)
    op.create_index(
        "fee_coordinator_external_id_idx",
        "fee",
        ["coordinator_external_id"],
        schema=SCHEMA,
    )
    op.create_index("fee_status_idx", "fee", ["status"], schema=SCHEMA)

    op.create_table(
        "fee_payment",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("fee_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("payment_id", sa.String(length=80), nullable=False),
        sa.Column("qrcode_payload", sa.Text(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("asaas_id", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="fee_payment_pkey"),
        schema=SCHEMA,
    )
    op.create_index("fee_payment_fee_id_idx", "fee_payment", ["fee_id"], schema=SCHEMA)
    op.create_index(
        "fee_payment_payment_id_idx",
        "fee_payment",
        ["payment_id"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_index("fee_payment_status_idx", "fee_payment", ["status"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("fee_payment", schema=SCHEMA)
    op.drop_table("fee", schema=SCHEMA)
