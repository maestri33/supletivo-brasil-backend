"""qrcode_url_to_asaas

Reescreve `lead.checkouts.qrcode_image` apontando do host antigo do `lead`
para o novo host do `asaas` (apos refactor que moveu persistencia do PNG).

Antes: URL relativa `/api/v1/public/media/qrcodes/<external_id>.png` (servida
pelo lead via StaticFiles em LEAD_PUBLIC_BASE_URL).

Depois: URL absoluta `<ASAAS_PUBLIC_BASE_URL>/api/v1/public/media/qrcodes/
<provider_payment_id>.png` (servida pelo asaas).

PRE-REQUISITO: scripts/migrate-qrcodes-to-asaas.sh deve ter rodado antes,
copiando os PNGs do volume `lead_media/qrcodes/` para `asaas_media/qrcodes/`
e renomeando `<external_id>.png` -> `<payment_id>.png`. Caso contrario as
URLs ficam apontando pra arquivos inexistentes (404 publico).

Revision ID: 0004
Revises: 0003
"""

import os
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_LEGACY_RELATIVE_PREFIXES = (
    "/api/v1/public/media/qrcodes/",
    "/media/qrcodes/",  # prefixo pre-StaticFiles refactor
)


def upgrade() -> None:
    asaas_base = os.environ.get("ASAAS_PUBLIC_BASE_URL")
    if not asaas_base:
        # Dev/CI tipicamente nao tem essa env setada — skip-com-stamp evita
        # bloquear o startup. Em prod, setar antes do deploy: a migration
        # roda de novo sem problema (idempotente via LIKE no qrcode_image).
        print(
            "[migration 0004] ASAAS_PUBLIC_BASE_URL ausente — skip rewrite. "
            "Re-rode com a env setada para migrar URLs legadas em prod."
        )
        return
    new_prefix = f"{asaas_base.rstrip('/')}/api/v1/public/media/qrcodes/"

    # Reescreve URLs apontando para o asaas + troca filename
    # (<external_id>.png -> <provider_payment_id>.png).
    #
    # Filtro: provider='asaas' AND qrcode_image LIKE prefixo legado.
    # Linhas com qrcode_image NULL ou ja-absoluta (https://...) sao ignoradas
    # pra preservar idempotencia em re-runs.
    conn = op.get_bind()
    stmt = text(
        """
        UPDATE lead.checkouts
           SET qrcode_image = :new_prefix || provider_payment_id || '.png'
         WHERE provider = 'asaas'
           AND provider_payment_id IS NOT NULL
           AND qrcode_image LIKE :legacy_pattern
        """
    )
    for legacy in _LEGACY_RELATIVE_PREFIXES:
        conn.execute(stmt, {"new_prefix": new_prefix, "legacy_pattern": f"{legacy}%"})


def downgrade() -> None:
    # Irreversivel sem tabela mapeando payment_id -> external_id original
    # E sem re-copiar os PNGs do asaas pro lead. Deixamos explicito em vez
    # de no-op pra evitar downgrade silencioso que quebra producao.
    raise RuntimeError(
        "downgrade nao suportado: requer re-copiar PNGs do asaas pro lead "
        "e renomear de <payment_id>.png -> <external_id>.png. Faca manualmente."
    )
