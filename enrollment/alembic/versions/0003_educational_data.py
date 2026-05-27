"""educational_data table

Tabela:
- enrollment.educational_data (1:1 com enrollments via enrollment_id UNIQUE)

PRD §4: dados educacionais ("último ano estudado, quando, em que escola") são
próprios do schema enrollment — não delegados a outro serviço.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "enrollment"


def upgrade() -> None:
    op.create_table(
        "educational_data",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_year_studied", sa.Integer(), nullable=False),
        sa.Column("last_year_date", sa.Date(), nullable=False),
        sa.Column("last_school", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="educational_data_pkey"),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            [f"{SCHEMA}.enrollments.id"],
            name="educational_data_enrollment_id_fkey",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("enrollment_id", name="educational_data_enrollment_id_key"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("educational_data", schema=SCHEMA)
