"""datetime columns -> timestamptz

Converte todas as colunas DateTime de TIMESTAMP WITHOUT TIME ZONE para
TIMESTAMP WITH TIME ZONE (timestamptz). O codigo sempre usou datetime.now(UTC)
(aware); psycopg2 tolerava, asyncpg nao aceita aware em coluna naive. Os
valores naive existentes sao interpretados como UTC na conversao.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "asaas"

# Todas as colunas DateTime do schema asaas (tabela, coluna).
_COLUMNS = [
    ("config", "updated_at"),
    ("url_verify_nonce", "created_at"),
    ("url_verify_nonce", "consumed_at"),
    ("webhook_event", "received_at"),
    ("webhook_event", "forwarded_at"),
    ("pix_key", "validated_at"),
    ("customer", "created_at"),
    ("customer", "updated_at"),
    ("payment", "scheduled_for"),
    ("payment", "created_at"),
    ("payment", "updated_at"),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
            schema=SCHEMA,
        )


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
            schema=SCHEMA,
        )
