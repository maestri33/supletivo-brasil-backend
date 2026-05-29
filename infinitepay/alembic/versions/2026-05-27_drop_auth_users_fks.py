"""drop FK cross-schema auth.users from infinitepay tables

Tabelas: checkouts, webhook_logs, outbound_jobs perdem a FK para auth.users.
Coluna external_id continua (UUID opaco, §4 da CONVENTION). Validação de
existencia do usuario, quando necessaria, passa a ser via HTTP no servico auth.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "infinitepay"


def upgrade() -> None:
    op.drop_constraint(
        "checkouts_external_id_fkey",
        "checkouts",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_constraint(
        "webhook_logs_external_id_fkey",
        "webhook_logs",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_constraint(
        "outbound_jobs_external_id_fkey",
        "outbound_jobs",
        schema=SCHEMA,
        type_="foreignkey",
    )


def downgrade() -> None:
    op.create_foreign_key(
        "checkouts_external_id_fkey",
        "checkouts",
        "users",
        ["external_id"],
        ["external_id"],
        source_schema=SCHEMA,
        referent_schema="auth",
        onupdate="CASCADE",
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "webhook_logs_external_id_fkey",
        "webhook_logs",
        "users",
        ["external_id"],
        ["external_id"],
        source_schema=SCHEMA,
        referent_schema="auth",
        onupdate="CASCADE",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "outbound_jobs_external_id_fkey",
        "outbound_jobs",
        "users",
        ["external_id"],
        ["external_id"],
        source_schema=SCHEMA,
        referent_schema="auth",
        onupdate="CASCADE",
        ondelete="SET NULL",
    )
