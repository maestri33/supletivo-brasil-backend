"""add templates table + log.external_id

Mudancas:
- Nova tabela notify.templates (slug unico, html, version, is_active)
- Seed do template `default` para preservar comportamento atual
- Nova coluna logs.external_id (UUID FK -> auth.users.external_id, RESTRICT)
  para suportar timeline por usuario sem JOIN obrigatorio em messages/contacts

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "notify"

# Template default — mesmo HTML do template_service legado, garante zero regressao.
_DEFAULT_TEMPLATE_HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f4f4f4;font-family:Arial,sans-serif">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;padding:20px 0">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden">
          <tr>
            <td style="padding:40px 48px">
              <h1 style="margin:0 0 16px;color:#1a1a1a;font-size:24px">{{title}}</h1>
              <div style="color:#333333;font-size:16px;line-height:1.6">
                {{content}}
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 48px;background-color:#f8f9fa;border-top:1px solid #e9ecef">
              <p style="margin:0;color:#6c757d;font-size:12px">
                supletivo.net.br
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="templates_pkey"),
        sa.UniqueConstraint("slug", name="templates_slug_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "templates_slug_idx", "templates", ["slug"], schema=SCHEMA, unique=False,
    )

    # Seed do template default — operador pode editar via PUT /templates/default
    templates = sa.table(
        "templates",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("html", sa.Text),
        sa.column("version", sa.Integer),
        sa.column("is_active", sa.Boolean),
        schema=SCHEMA,
    )
    op.bulk_insert(
        templates,
        [
            {
                "slug": "default",
                "name": "Template padrao",
                "html": _DEFAULT_TEMPLATE_HTML,
                "version": 1,
                "is_active": True,
            },
        ],
    )

    # logs.external_id — timeline por usuario sem JOIN obrigatorio
    op.add_column(
        "logs",
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "logs_external_id_fkey",
        "logs", "users",
        ["external_id"], ["external_id"],
        source_schema=SCHEMA, referent_schema="auth",
        onupdate="CASCADE", ondelete="RESTRICT",
    )
    op.create_index(
        "logs_external_id_idx", "logs", ["external_id"], schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("logs_external_id_idx", table_name="logs", schema=SCHEMA)
    op.drop_constraint(
        "logs_external_id_fkey", "logs", schema=SCHEMA, type_="foreignkey",
    )
    op.drop_column("logs", "external_id", schema=SCHEMA)

    op.drop_index("templates_slug_idx", table_name="templates", schema=SCHEMA)
    op.drop_table("templates", schema=SCHEMA)
