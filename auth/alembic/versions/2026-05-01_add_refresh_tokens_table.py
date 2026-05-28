"""add refresh_tokens table

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
        ),
        sa.Column(
            "identity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("auth.identities.external_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "family_id",
            UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_table("refresh_tokens", schema="auth")
