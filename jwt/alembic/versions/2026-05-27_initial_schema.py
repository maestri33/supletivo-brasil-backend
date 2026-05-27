"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-27
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "jwt"')


def downgrade() -> None:
    op.execute('DROP SCHEMA IF EXISTS "jwt" CASCADE')
