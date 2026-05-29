"""add failed status + failed_reason

Acrescenta o valor 'failed' no enum lead_status e a coluna leads.failed_reason
(usados quando o BG task de criar checkout esgota retries — front polla
/waiting e recebe error_code).

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-28
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "lead"


def upgrade() -> None:
    # ALTER TYPE precisa rodar fora de transação no Postgres < 12 e e' idempotente
    # em pg >= 12. Aqui usamos op.execute direto (Alembic abre tx por migration).
    op.execute(f"ALTER TYPE {SCHEMA}.lead_status ADD VALUE IF NOT EXISTS 'failed'")

    op.add_column(
        "leads",
        sa.Column("failed_reason", sa.String(length=80), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("leads", "failed_reason", schema=SCHEMA)
    # Remover valor de enum em Postgres exige recriar o tipo — caro e
    # arriscado em produção. Como o downgrade aqui e' so para dev/testes,
    # deixamos o valor 'failed' no enum (no-op) e so removemos a coluna.
