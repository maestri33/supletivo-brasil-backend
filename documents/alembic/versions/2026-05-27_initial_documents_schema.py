"""initial documents schema

Tabelas `documentos`, `rg`, `cnh`, `carteiras_trabalho`, `passaportes`
no schema `documents`.

PK = UUID (gerada na app, default uuid4). `external_id` e' o UUID do usuario
emitido pelo auth — referencia logica, sem FK cross-schema. Datas usam
timestamptz com server_default=now().

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

    # ── documentos (aggregate root) ──
    op.create_table(
        "documentos",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("external_id", postgresql.UUID(), nullable=False),
        sa.Column("rg_id", postgresql.UUID(), nullable=True),
        sa.Column("cnh_id", postgresql.UUID(), nullable=True),
        sa.Column("carteira_trabalho_id", postgresql.UUID(), nullable=True),
        sa.Column("passaporte_id", postgresql.UUID(), nullable=True),
        # Certidao
        sa.Column("certidao_tipo", sa.String(length=20), nullable=True),
        sa.Column("certidao_numero", sa.String(length=50), nullable=True),
        sa.Column("certidao_cartorio", sa.String(length=100), nullable=True),
        sa.Column("certidao_livro", sa.String(length=20), nullable=True),
        sa.Column("certidao_folha", sa.String(length=20), nullable=True),
        sa.Column("certidao_termo", sa.String(length=20), nullable=True),
        sa.Column("certidao_data_emissao", sa.Date(), nullable=True),
        sa.Column("certidao_foto", sa.String(length=500), nullable=True),
        # Reservista
        sa.Column("reservista_numero", sa.String(length=30), nullable=True),
        sa.Column("reservista_serie", sa.String(length=20), nullable=True),
        sa.Column("reservista_categoria", sa.String(length=20), nullable=True),
        sa.Column("reservista_ra", sa.String(length=20), nullable=True),
        sa.Column("reservista_foto", sa.String(length=500), nullable=True),
        # Comprovante
        sa.Column("comprovante_residencia_foto", sa.String(length=500), nullable=True),
        # Foto geral
        sa.Column("foto", sa.String(length=500), nullable=True),
        # Timestamps
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
        sa.PrimaryKeyConstraint("id", name="documentos_pkey"),
        sa.UniqueConstraint("external_id", name="documentos_external_id_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "documentos_external_id_idx",
        "documentos",
        ["external_id"],
        unique=True,
        schema=SCHEMA,
    )

    # ── rg ──
    op.create_table(
        "rg",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("numero", sa.String(length=30), nullable=True),
        sa.Column("orgao_emissor", sa.String(length=50), nullable=True),
        sa.Column("data_emissao", sa.Date(), nullable=True),
        sa.Column("foto_frente", sa.String(length=500), nullable=True),
        sa.Column("foto_verso", sa.String(length=500), nullable=True),
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

    # ── cnh ──
    op.create_table(
        "cnh",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("numero", sa.String(length=30), nullable=True),
        sa.Column("categoria", sa.String(length=5), nullable=True),
        sa.Column("data_nascimento", sa.Date(), nullable=True),
        sa.Column("validade", sa.Date(), nullable=True),
        sa.Column("registro_nacional", sa.String(length=30), nullable=True),
        sa.Column("foto_frente", sa.String(length=500), nullable=True),
        sa.Column("foto_verso", sa.String(length=500), nullable=True),
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

    # ── carteiras_trabalho ──
    op.create_table(
        "carteiras_trabalho",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("numero", sa.String(length=30), nullable=True),
        sa.Column("serie", sa.String(length=20), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("data_emissao", sa.Date(), nullable=True),
        sa.Column("foto_frente", sa.String(length=500), nullable=True),
        sa.Column("foto_verso", sa.String(length=500), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="carteiras_trabalho_pkey"),
        schema=SCHEMA,
    )

    # ── passaportes ──
    op.create_table(
        "passaportes",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("numero", sa.String(length=30), nullable=True),
        sa.Column("validade", sa.Date(), nullable=True),
        sa.Column("data_emissao", sa.Date(), nullable=True),
        sa.Column("foto_frente", sa.String(length=500), nullable=True),
        sa.Column("foto_verso", sa.String(length=500), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="passaportes_pkey"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("passaportes", schema=SCHEMA)
    op.drop_table("carteiras_trabalho", schema=SCHEMA)
    op.drop_table("cnh", schema=SCHEMA)
    op.drop_table("rg", schema=SCHEMA)
    op.drop_table("documentos", schema=SCHEMA)
