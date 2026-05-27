"""rename_identities_to_users

Revision ID: c832fc1a6459
Revises: 0006
Create Date: 2026-05-09 11:07:57.240202
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c832fc1a6459"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop FKs
    op.execute("ALTER TABLE auth.identity_roles DROP CONSTRAINT identity_roles_identity_id_fkey")
    op.execute("ALTER TABLE auth.refresh_tokens DROP CONSTRAINT refresh_tokens_identity_id_fkey")

    # Rename tables
    op.execute("ALTER TABLE auth.identities RENAME TO users")
    op.execute("ALTER TABLE auth.identity_roles RENAME TO user_roles")

    # Rename columns
    op.execute("ALTER TABLE auth.user_roles RENAME COLUMN identity_id TO user_id")
    op.execute("ALTER TABLE auth.refresh_tokens RENAME COLUMN identity_id TO user_id")

    # Rename indexes
    op.execute("ALTER INDEX auth.identities_pkey RENAME TO users_pkey")
    op.execute("ALTER INDEX auth.identities_id_external_key RENAME TO users_id_external_key")
    op.execute("ALTER INDEX auth.identity_roles_pkey RENAME TO user_roles_pkey")

    # Re-create FKs
    op.execute(
        "ALTER TABLE auth.user_roles ADD CONSTRAINT user_roles_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES auth.users (external_id) ON DELETE CASCADE"
    )
    op.execute(
        "ALTER TABLE auth.refresh_tokens ADD CONSTRAINT refresh_tokens_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES auth.users (external_id) ON DELETE CASCADE"
    )


def downgrade() -> None:
    # Drop FKs
    op.execute("ALTER TABLE auth.user_roles DROP CONSTRAINT user_roles_user_id_fkey")
    op.execute("ALTER TABLE auth.refresh_tokens DROP CONSTRAINT refresh_tokens_user_id_fkey")

    # Rename columns back
    op.execute("ALTER TABLE auth.user_roles RENAME COLUMN user_id TO identity_id")
    op.execute("ALTER TABLE auth.refresh_tokens RENAME COLUMN user_id TO identity_id")

    # Rename tables back
    op.execute("ALTER TABLE auth.users RENAME TO identities")
    op.execute("ALTER TABLE auth.user_roles RENAME TO identity_roles")

    # Rename indexes back
    op.execute("ALTER INDEX auth.users_pkey RENAME TO identities_pkey")
    op.execute("ALTER INDEX auth.users_id_external_key RENAME TO identities_id_external_key")
    op.execute("ALTER INDEX auth.user_roles_pkey RENAME TO identity_roles_pkey")

    # Re-create FKs
    op.execute(
        "ALTER TABLE auth.identity_roles ADD CONSTRAINT identity_roles_identity_id_fkey "
        "FOREIGN KEY (identity_id) REFERENCES auth.identities (external_id) ON DELETE CASCADE"
    )
    op.execute(
        "ALTER TABLE auth.refresh_tokens ADD CONSTRAINT refresh_tokens_identity_id_fkey "
        "FOREIGN KEY (identity_id) REFERENCES auth.identities (external_id) ON DELETE CASCADE"
    )
