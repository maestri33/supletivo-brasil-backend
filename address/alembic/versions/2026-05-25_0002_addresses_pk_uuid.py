"""addresses PK integer -> UUID

Troca a PK das 3 tabelas do schema `addresses` de integer/autoincrement para
UUID (CONVENTION §4). `external_id` já era UUID e permanece. Estratégia
greenfield: drop + recreate (0001 é o schema inicial, sem dados de produção a
preservar). A PK passa a ser gerada na aplicação (`default=uuid4` nos models),
então a coluna UUID não precisa de server_default.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "addresses"


def _id_col() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False)


def _id_col_int() -> sa.Column:
    return sa.Column("id", sa.Integer(), autoincrement=True, nullable=False)


def _addr_fk_col(as_uuid: bool) -> sa.Column:
    col_type = postgresql.UUID(as_uuid=True) if as_uuid else sa.Integer()
    return sa.Column("address_id", col_type, nullable=True)


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
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
    )


def _create_all(as_uuid: bool) -> None:
    id_col = _id_col if as_uuid else _id_col_int
    created_at, updated_at = _timestamps()

    op.create_table(
        "addresses",
        id_col(),
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
        created_at,
        updated_at,
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

    created_at, updated_at = _timestamps()
    op.create_table(
        "entity_address_details",
        id_col(),
        sa.Column("street", sa.String(length=200), nullable=True),
        sa.Column("number", sa.String(length=20), nullable=True),
        sa.Column("complement", sa.String(length=100), nullable=True),
        sa.Column("neighborhood", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("zipcode", sa.String(length=8), nullable=True),
        sa.Column("lat", sa.String(length=30), nullable=True),
        sa.Column("lng", sa.String(length=30), nullable=True),
        created_at,
        updated_at,
        sa.PrimaryKeyConstraint("id", name="entity_address_details_pkey"),
        schema=SCHEMA,
    )

    created_at, updated_at = _timestamps()
    op.create_table(
        "entity_addresses",
        id_col(),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("proof_file", sa.String(length=255), nullable=True),
        _addr_fk_col(as_uuid),
        created_at,
        updated_at,
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


def _drop_all() -> None:
    # Ordem por dependência de FK; índices caem junto com a tabela.
    op.drop_table("entity_addresses", schema=SCHEMA)
    op.drop_table("entity_address_details", schema=SCHEMA)
    op.drop_table("addresses", schema=SCHEMA)


def upgrade() -> None:
    _drop_all()
    _create_all(as_uuid=True)


def downgrade() -> None:
    _drop_all()
    _create_all(as_uuid=False)
