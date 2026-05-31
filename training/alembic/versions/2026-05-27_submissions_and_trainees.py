"""submissions and trainees

Cria as tabelas `submissions` (tentativa de resposta do trainee) e `trainees`
(estado do candidato dentro da trilha de treinamento, transicoes do coordenador).

Sem FK cross-schema: `external_id` (UUID) referencia logicamente `auth.users`.
FK local: `submissions.material_id` -> `materials.id` (mesmo schema).

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "training"


def upgrade() -> None:
    op.create_table(
        "trainees",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("coordinator_external_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("coordinator_decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("awaiting_interview_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="trainees_pkey"),
        sa.UniqueConstraint("external_id", name="trainees_external_id_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "external_id_idx",
        "trainees",
        ["external_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "status_idx",
        "trainees",
        ["status"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("grade", sa.Float(), nullable=True),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="submissions_pkey"),
        sa.ForeignKeyConstraint(
            ["material_id"],
            [f"{SCHEMA}.materials.id"],
            name="submissions_material_id_fkey",
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "submissions_external_id_idx",
        "submissions",
        ["external_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "submissions_material_id_idx",
        "submissions",
        ["material_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "submissions_status_idx",
        "submissions",
        ["status"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "submissions_external_material_idx",
        "submissions",
        ["external_id", "material_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("submissions_external_material_idx", table_name="submissions", schema=SCHEMA)
    op.drop_index("submissions_status_idx", table_name="submissions", schema=SCHEMA)
    op.drop_index("submissions_material_id_idx", table_name="submissions", schema=SCHEMA)
    op.drop_index("submissions_external_id_idx", table_name="submissions", schema=SCHEMA)
    op.drop_table("submissions", schema=SCHEMA)
    op.drop_index("status_idx", table_name="trainees", schema=SCHEMA)
    op.drop_index("external_id_idx", table_name="trainees", schema=SCHEMA)
    op.drop_table("trainees", schema=SCHEMA)
