"""replace_auth_users_with_identity_role_tables

Revision ID: 0002
Revises: 28fa322e19a2
Create Date: 2026-05-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = '0002'
down_revision: Union[str, None] = '28fa322e19a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('users', schema='auth')

    op.create_table(
        'identities',
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('id_external', UUID(), nullable=False, unique=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema='auth',
    )

    op.create_table(
        'identity_roles',
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('identity_id', UUID(), sa.ForeignKey('auth.identities.id_external', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        schema='auth',
    )

    op.create_table(
        'role_rules',
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('from_role', sa.String(), nullable=True),
        sa.Column('to_role', sa.String(), nullable=False),
        sa.Column('mode', sa.String(), nullable=False),
        sa.Column('requires_role', sa.String(), nullable=True),
        schema='auth',
    )

    # Seed das 6 regras
    op.execute(sa.text(
        "INSERT INTO auth.role_rules (from_role, to_role, mode, requires_role) VALUES "
        "(NULL, 'a', 'add', NULL),"
        "(NULL, 'x', 'add', NULL),"
        "('a', 'b', 'replace', NULL),"
        "('x', 'y', 'replace', NULL),"
        "(NULL, 'c', 'add', 'b'),"
        "(NULL, 'z', 'add', 'y')"
    ))


def downgrade() -> None:
    op.drop_table('role_rules', schema='auth')
    op.drop_table('identity_roles', schema='auth')
    op.drop_table('identities', schema='auth')

    op.create_table(
        'users',
        sa.Column('id', UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('id_external', UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id_external'),
        schema='auth',
    )
