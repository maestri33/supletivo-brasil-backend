"""trigger updated_at em profiles.profiles

O ORM já seta updated_at via `onupdate=func.now()` em toda escrita pelo
SQLAlchemy. Este trigger garante o mesmo comportamento para UPDATE por SQL
direto (manutenção, scripts), que o ORM não cobre.

Aplica-se só a `profiles.profiles` — birth_info e educational não têm o campo.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "profiles"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.set_updated_at()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER profiles_set_updated_at
        BEFORE UPDATE ON {SCHEMA}.profiles
        FOR EACH ROW
        EXECUTE FUNCTION {SCHEMA}.set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute(
        f"DROP TRIGGER IF EXISTS profiles_set_updated_at ON {SCHEMA}.profiles"
    )
    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}.set_updated_at()")
