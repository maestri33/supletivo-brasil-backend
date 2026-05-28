"""enrollment aggregate

Tabela:
- enrollment.enrollments (agregado de matrícula; FK external_id -> auth.users.external_id)

PK UUID (CONVENTION §4). Criado a partir do webhook `lead.completed`; guarda o
status da matrícula e os vínculos (matriculando, promotor, hub).

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


SCHEMA = "enrollment"


def upgrade() -> None:
    op.create_table(
        "enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("promoter_external_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("hub_external_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="enrollments_pkey"),
        schema=SCHEMA,
    )
    op.create_index(
        "enrollments_external_id_idx",
        "enrollments",
        ["external_id"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_index(
        "enrollments_status_idx",
        "enrollments",
        ["status"],
        schema=SCHEMA,
    )
    op.create_index(
        "enrollments_promoter_external_id_idx",
        "enrollments",
        ["promoter_external_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "enrollments_hub_external_id_idx",
        "enrollments",
        ["hub_external_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("enrollments", schema=SCHEMA)
