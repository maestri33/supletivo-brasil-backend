"""initial roles schema

Tabelas:
- roles.role_rules
- roles.user_roles (FK external_id -> auth.users.external_id)

Revision ID: 0001
Revises:
Create Date: 2026-05-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "roles"


def upgrade() -> None:
    op.create_table(
        "role_rules",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("from_role", sa.String(length=64), nullable=True),
        sa.Column("to_role", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("requires_role", sa.String(length=64), nullable=True),
        sa.Column("forbids_role", sa.String(length=64), nullable=True),
        sa.Column(
            "blocking", sa.Boolean(),
            server_default=sa.text("false"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="role_rules_pkey"),
        schema=SCHEMA,
    )

    op.create_table(
        "user_roles",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column(
            "assigned_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="user_roles_pkey"),
        sa.ForeignKeyConstraint(
            ["external_id"], ["auth.users.external_id"],
            name="user_roles_external_id_fkey",
            onupdate="CASCADE", ondelete="RESTRICT",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "user_roles_external_id_idx", "user_roles", ["external_id"], schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("user_roles", schema=SCHEMA)
    op.drop_table("role_rules", schema=SCHEMA)
