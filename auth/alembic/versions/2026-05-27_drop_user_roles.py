"""drop user_roles table from auth

§8 da CONVENTION: somente o app `roles` mantém tabela de roles. `auth` mantém
apenas a tabela `users`. Esta migração remove `auth.user_roles` em produção.

Revision ID: 0007
Revises: c832fc1a6459
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007"
down_revision: str | None = "c832fc1a6459"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("user_roles", schema="auth")


def downgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="user_roles_pkey"),
        schema="auth",
    )
