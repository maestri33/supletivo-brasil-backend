"""initial staff schema

Schema `staff` — cria o schema sem tabelas no milestone 1.
Modelos de domínio entram nos milestones 4/5.

Revision ID: 0001
Revises:
Create Date: 2026-05-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "staff"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")


def downgrade() -> None:
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
