"""rename_id_external_to_external_id_drop_phone

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-01
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("ALTER TABLE auth.identity_roles DROP CONSTRAINT identity_roles_identity_id_fkey")
    )
    op.alter_column("identities", "id_external", new_column_name="external_id", schema="auth")
    op.execute(
        sa.text(
            "ALTER TABLE auth.identity_roles ADD CONSTRAINT identity_roles_identity_id_fkey "
            "FOREIGN KEY (identity_id) REFERENCES auth.identities (external_id) ON DELETE CASCADE"
        )
    )
    op.drop_column("identities", "phone", schema="auth")


def downgrade() -> None:
    op.add_column("identities", sa.Column("phone", sa.String(), nullable=True), schema="auth")
    op.execute(
        sa.text("ALTER TABLE auth.identity_roles DROP CONSTRAINT identity_roles_identity_id_fkey")
    )
    op.alter_column("identities", "external_id", new_column_name="id_external", schema="auth")
    op.execute(
        sa.text(
            "ALTER TABLE auth.identity_roles ADD CONSTRAINT identity_roles_identity_id_fkey "
            "FOREIGN KEY (identity_id) REFERENCES auth.identities (id_external) ON DELETE CASCADE"
        )
    )
