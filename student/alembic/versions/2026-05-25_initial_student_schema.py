"""initial student schema

Tabela student.students — funil do aluno. PK UUID (gerada na app), FK
cross-schema para auth.users.external_id (§4). status como VARCHAR (enum
nao-nativo) e study_platform como JSONB. Datas em timestamptz.

Revision ID: 0001
Revises:
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "student"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "students",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("study_platform", postgresql.JSONB(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="students_pkey"),
        sa.UniqueConstraint("external_id", name="students_external_id_key"),
        schema=SCHEMA,
    )
    op.create_index("students_external_id_idx", "students", ["external_id"], schema=SCHEMA)
    op.create_index("students_status_idx", "students", ["status"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("students_status_idx", table_name="students", schema=SCHEMA)
    op.drop_index("students_external_id_idx", table_name="students", schema=SCHEMA)
    op.drop_table("students", schema=SCHEMA)
