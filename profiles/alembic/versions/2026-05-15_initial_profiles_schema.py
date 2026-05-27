"""initial profiles schema

Tabelas:
- profiles.profiles      (FK external_id -> auth.users.external_id)
- profiles.birth_info    (FK profile_id  -> profiles.profiles.id, CASCADE)
- profiles.educational   (FK profile_id  -> profiles.profiles.id, CASCADE)

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


SCHEMA = "profiles"


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cpf", sa.String(length=11), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("gender", sa.String(length=1), nullable=True),
        sa.Column("mother_name", sa.String(length=200), nullable=True),
        sa.Column("father_name", sa.String(length=200), nullable=True),
        sa.Column("blood_type", sa.String(length=3), nullable=True),
        sa.Column("civil_status", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="profiles_pkey"),
        sa.UniqueConstraint("external_id", name="profiles_external_id_key"),
        sa.UniqueConstraint("cpf", name="profiles_cpf_key"),
        sa.ForeignKeyConstraint(
            ["external_id"],
            ["auth.users.external_id"],
            name="profiles_external_id_fkey",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "birth_info",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="birth_info_pkey"),
        sa.UniqueConstraint("profile_id", name="birth_info_profile_id_key"),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            [f"{SCHEMA}.profiles.id"],
            name="birth_info_profile_id_fkey",
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "educational",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=30), nullable=True),
        sa.Column("last_elementary_year", sa.String(length=10), nullable=True),
        sa.Column("elementary_completed", sa.Boolean(), nullable=True),
        sa.Column("elementary_year", sa.Integer(), nullable=True),
        sa.Column("last_high_school_year", sa.String(length=15), nullable=True),
        sa.Column("high_school_completed", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="educational_pkey"),
        sa.UniqueConstraint("profile_id", name="educational_profile_id_key"),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            [f"{SCHEMA}.profiles.id"],
            name="educational_profile_id_fkey",
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("educational", schema=SCHEMA)
    op.drop_table("birth_info", schema=SCHEMA)
    op.drop_table("profiles", schema=SCHEMA)
