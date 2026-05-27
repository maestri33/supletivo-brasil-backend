"""initial documents schema

Tabelas `documents`, `rg`, `cnh`, `work_cards`, `passports` no schema `documents`.

PK = UUID (gerada na app, default uuid4). `external_id` e' o UUID do usuario
emitido pelo auth — referencia logica, sem FK cross-schema (§4). Identificadores
em ingles (§15); valores como `certificate_kind` podem ficar em pt-br por
corresponder ao dado de mundo real (nascimento/casamento/obito).

Revision ID: 0001
Revises:
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "documents"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    # ── documents (aggregate root) ──
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("external_id", postgresql.UUID(), nullable=False),
        sa.Column("rg_id", postgresql.UUID(), nullable=True),
        sa.Column("cnh_id", postgresql.UUID(), nullable=True),
        sa.Column("work_card_id", postgresql.UUID(), nullable=True),
        sa.Column("passport_id", postgresql.UUID(), nullable=True),
        sa.Column("certificate_kind", sa.String(length=20), nullable=True),
        sa.Column("certificate_number", sa.String(length=50), nullable=True),
        sa.Column("certificate_registry_office", sa.String(length=100), nullable=True),
        sa.Column("certificate_book", sa.String(length=20), nullable=True),
        sa.Column("certificate_page", sa.String(length=20), nullable=True),
        sa.Column("certificate_entry", sa.String(length=20), nullable=True),
        sa.Column("certificate_issue_date", sa.Date(), nullable=True),
        sa.Column("certificate_photo", sa.String(length=500), nullable=True),
        sa.Column("military_number", sa.String(length=30), nullable=True),
        sa.Column("military_series", sa.String(length=20), nullable=True),
        sa.Column("military_category", sa.String(length=20), nullable=True),
        sa.Column("military_ra", sa.String(length=20), nullable=True),
        sa.Column("military_photo", sa.String(length=500), nullable=True),
        sa.Column("proof_of_residence_photo", sa.String(length=500), nullable=True),
        sa.Column("photo", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="documents_pkey"),
        sa.UniqueConstraint("external_id", name="documents_external_id_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "documents_external_id_idx",
        "documents",
        ["external_id"],
        unique=True,
        schema=SCHEMA,
    )

    op.create_table(
        "rg",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("number", sa.String(length=30), nullable=True),
        sa.Column("issuing_agency", sa.String(length=50), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("front_photo", sa.String(length=500), nullable=True),
        sa.Column("back_photo", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="rg_pkey"),
        schema=SCHEMA,
    )

    op.create_table(
        "cnh",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("number", sa.String(length=30), nullable=True),
        sa.Column("category", sa.String(length=5), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("national_register", sa.String(length=30), nullable=True),
        sa.Column("front_photo", sa.String(length=500), nullable=True),
        sa.Column("back_photo", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="cnh_pkey"),
        schema=SCHEMA,
    )

    op.create_table(
        "work_cards",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("number", sa.String(length=30), nullable=True),
        sa.Column("series", sa.String(length=20), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("front_photo", sa.String(length=500), nullable=True),
        sa.Column("back_photo", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="work_cards_pkey"),
        schema=SCHEMA,
    )

    op.create_table(
        "passports",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("number", sa.String(length=30), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("front_photo", sa.String(length=500), nullable=True),
        sa.Column("back_photo", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="passports_pkey"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("passports", schema=SCHEMA)
    op.drop_table("work_cards", schema=SCHEMA)
    op.drop_table("cnh", schema=SCHEMA)
    op.drop_table("rg", schema=SCHEMA)
    op.drop_table("documents", schema=SCHEMA)
