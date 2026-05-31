"""initial addresses schema

Tabelas (schema `addresses`):
- addresses              (FK external_id -> auth.users.external_id; + lat/lng do LOCAL)
- entity_address_details (endereço genérico nullable — feature do LOCAL)
- entity_addresses       (vínculo polimórfico (entity_type, external_id) -> details)

Revision ID: 0001
Revises:
Create Date: 2026-05-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "addresses"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "addresses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("zipcode", sa.String(length=8), nullable=False),
        sa.Column("street", sa.String(length=200), nullable=False),
        sa.Column("number", sa.String(length=20), nullable=True),
        sa.Column("complement", sa.String(length=100), nullable=True),
        sa.Column("neighborhood", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column(
            "country",
            sa.String(length=2),
            server_default=sa.text("'BR'"),
            nullable=False,
        ),
        sa.Column("lat", sa.String(length=30), nullable=True),
        sa.Column("lng", sa.String(length=30), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="addresses_pkey"),
        sa.ForeignKeyConstraint(
            ["external_id"],
            ["auth.users.external_id"],
            name="addresses_external_id_fkey",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        schema=SCHEMA,
    )

    op.create_index("addresses_external_id_idx", "addresses", ["external_id"], schema=SCHEMA)
    op.create_index("addresses_kind_idx", "addresses", ["kind"], schema=SCHEMA)
    op.create_index("addresses_zipcode_idx", "addresses", ["zipcode"], schema=SCHEMA)
    op.create_index(
        "addresses_external_id_kind_idx",
        "addresses",
        ["external_id", "kind"],
        schema=SCHEMA,
    )

    op.create_table(
        "entity_address_details",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("street", sa.String(length=200), nullable=True),
        sa.Column("number", sa.String(length=20), nullable=True),
        sa.Column("complement", sa.String(length=100), nullable=True),
        sa.Column("neighborhood", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("zipcode", sa.String(length=8), nullable=True),
        sa.Column("lat", sa.String(length=30), nullable=True),
        sa.Column("lng", sa.String(length=30), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="entity_address_details_pkey"),
        schema=SCHEMA,
    )

    op.create_table(
        "entity_addresses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("proof_file", sa.String(length=255), nullable=True),
        sa.Column("address_id", sa.Integer(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="entity_addresses_pkey"),
        sa.ForeignKeyConstraint(
            ["address_id"],
            [f"{SCHEMA}.entity_address_details.id"],
            name="entity_addresses_address_id_fkey",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("entity_type", "external_id", name="entity_addresses_entity_key"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("entity_addresses", schema=SCHEMA)
    op.drop_table("entity_address_details", schema=SCHEMA)
    op.drop_index("addresses_external_id_kind_idx", table_name="addresses", schema=SCHEMA)
    op.drop_index("addresses_zipcode_idx", table_name="addresses", schema=SCHEMA)
    op.drop_index("addresses_kind_idx", table_name="addresses", schema=SCHEMA)
    op.drop_index("addresses_external_id_idx", table_name="addresses", schema=SCHEMA)
    op.drop_table("addresses", schema=SCHEMA)
