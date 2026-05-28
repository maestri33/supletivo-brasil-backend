"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-27
"""  # noqa: N999

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "jwt"')


def downgrade() -> None:
    op.execute('DROP SCHEMA IF EXISTS "jwt" CASCADE')
