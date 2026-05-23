"""indexes for search and listing

Adiciona índices que aceleram:
- busca prefix por name (GET /api/v1/profiles?q=...)
- listagem ordenada por created_at desc (default da paginação)

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-15
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "profiles"


def upgrade() -> None:
    # btree(name) com case-insensitive via lower() — casa com ILIKE/lower-LIKE
    op.execute(
        f"CREATE INDEX IF NOT EXISTS profiles_name_lower_idx "
        f"ON {SCHEMA}.profiles (lower(name))",
    )
    op.create_index(
        "profiles_created_at_idx",
        "profiles",
        ["created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("profiles_created_at_idx", table_name="profiles", schema=SCHEMA)
    op.execute(f"DROP INDEX IF EXISTS {SCHEMA}.profiles_name_lower_idx")
