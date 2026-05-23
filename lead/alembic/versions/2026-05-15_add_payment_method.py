"""add payment_method + asaas charge fields to lead.checkouts

Acrescenta colunas para suportar PIX (asaas) lado a lado com cartao (infinitepay):
- payment_method: 'credit_card' | 'pix' (escolhido no captured POST)
- provider: 'infinitepay' | 'asaas'
- provider_payment_id: id retornado pelo provider, indexado para lookup no webhook
- qrcode_payload: BR Code copia-e-cola (PIX)
- qrcode_image: PNG base64 do QR Code (PIX)
- due_date: vencimento da cobranca PIX

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-15
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "lead"


def upgrade() -> None:
    op.add_column(
        "checkouts",
        sa.Column("payment_method", sa.String(length=20), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "checkouts",
        sa.Column("provider", sa.String(length=20), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "checkouts",
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "checkouts",
        sa.Column("qrcode_payload", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "checkouts",
        sa.Column("qrcode_image", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "checkouts",
        sa.Column("due_date", sa.Date(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "checkouts_provider_payment_id_idx",
        "checkouts",
        ["provider_payment_id"],
        schema=SCHEMA,
    )

    # Backfill linhas legadas: pre-0002 so existia infinitepay/cartao.
    # Necessario para que o webhook /asaas-charge possa rejeitar com seguranca
    # checkouts de OUTROS providers (provider != 'asaas').
    op.execute(
        """
        UPDATE lead.checkouts
           SET provider = 'infinitepay',
               payment_method = 'credit_card'
         WHERE provider IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index(
        "checkouts_provider_payment_id_idx", table_name="checkouts", schema=SCHEMA
    )
    op.drop_column("checkouts", "due_date", schema=SCHEMA)
    op.drop_column("checkouts", "qrcode_image", schema=SCHEMA)
    op.drop_column("checkouts", "qrcode_payload", schema=SCHEMA)
    op.drop_column("checkouts", "provider_payment_id", schema=SCHEMA)
    op.drop_column("checkouts", "provider", schema=SCHEMA)
    op.drop_column("checkouts", "payment_method", schema=SCHEMA)
