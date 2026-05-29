"""Initial schema — creates coordinator schema if not exists.

No tables yet; this migration only ensures the schema exists so that
future migrations can create tables within it.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "2026-05-27_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "coordinator"')


def downgrade() -> None:
    op.execute('DROP SCHEMA IF EXISTS "coordinator" CASCADE')
