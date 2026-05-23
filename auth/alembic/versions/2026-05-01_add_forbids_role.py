"""add_forbids_role_to_role_rules

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-01
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('role_rules', sa.Column('forbids_role', sa.String(), nullable=True), schema='auth')


def downgrade() -> None:
    op.drop_column('role_rules', 'forbids_role', schema='auth')
