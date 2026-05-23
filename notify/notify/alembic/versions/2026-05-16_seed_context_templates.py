"""seed context templates (welcome, checkout, receipt, parabens)

Insere variantes do template `default` com paletas diferenciadas por
contexto. Idempotente: usa INSERT ... ON CONFLICT (slug) DO NOTHING.

Operador pode editar/customizar depois via PUT /api/v1/templates/<slug>
(manual ou com instrucao para IA).

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-16
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "notify"


def _template_html(accent_color: str, footer_label: str) -> str:
    """Variante do template default com cor de destaque e label no rodape."""
    return f"""\
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
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden;border-top:4px solid {accent_color}">
          <tr>
            <td style="padding:40px 48px">
              <h1 style="margin:0 0 16px;color:{accent_color};font-size:24px">{{{{title}}}}</h1>
              <div style="color:#333333;font-size:16px;line-height:1.6">
                {{{{content}}}}
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 48px;background-color:#f8f9fa;border-top:1px solid #e9ecef">
              <p style="margin:0;color:#6c757d;font-size:12px">
                {footer_label} · supletivo.net.br
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


_SEEDS = [
    {
        "slug": "welcome",
        "name": "Boas-vindas",
        # Azul — acolhimento
        "html": _template_html("#1a73e8", "Bem-vindo(a)"),
    },
    {
        "slug": "checkout",
        "name": "Link de checkout",
        # Ambar — chamada para acao
        "html": _template_html("#d97706", "Finalize sua compra"),
    },
    {
        "slug": "receipt",
        "name": "Recibo de pagamento",
        # Verde — confirmacao
        "html": _template_html("#16a34a", "Pagamento confirmado"),
    },
    {
        "slug": "parabens",
        "name": "Parabens / celebracao",
        # Roxo — celebracao
        "html": _template_html("#7c3aed", "Voce conseguiu!"),
    },
]


def upgrade() -> None:
    # ON CONFLICT (slug) DO NOTHING — operador pode ter customizado um
    # slug antes desta migration; nao sobrescrevemos.
    for seed in _SEEDS:
        op.execute(
            sa.text(
                f"INSERT INTO {SCHEMA}.templates (slug, name, html, version, is_active) "
                "VALUES (:slug, :name, :html, 1, true) "
                "ON CONFLICT (slug) DO NOTHING"
            ).bindparams(
                slug=seed["slug"],
                name=seed["name"],
                html=seed["html"],
            )
        )


def downgrade() -> None:
    # Remove apenas os slugs criados aqui — se operador customizou
    # (version > 1), preserva sob a heuristica conservadora.
    slugs = [s["slug"] for s in _SEEDS]
    op.execute(
        sa.text(
            f"DELETE FROM {SCHEMA}.templates WHERE slug = ANY(:slugs) AND version = 1"
        ).bindparams(slugs=slugs)
    )
