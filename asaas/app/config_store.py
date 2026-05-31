"""Typed accessors over the ConfigKV table.

A tabela `asaas.config` armazena config operacional (security token derivado
do Asaas, account name, internal URLs, etc). Para sobreviver a wipes, o
lifespan no main.py chama `seed_from_env(db)` no startup — copia env vars
pra DB se a tabela esta vazia. Veja services/asaas/app/config.py.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import ConfigKV

# Known keys
K_EXTERNAL_URL = "external_url"  # URL publica base do asaas-app
K_ASAAS_API_KEY = "asaas_api_key"
K_ASAAS_SECURITY_TOKEN = "asaas_security_token"  # token do mecanismo de seguranca
K_ASAAS_WALLET_ID = "asaas_wallet_id"
K_ASAAS_ACCOUNT_NAME = "asaas_account_name"
K_ASAAS_WEBHOOK_SECRET = "asaas_webhook_secret"  # HMAC secret para validar webhooks

# Notificacoes internas — 3 destinos separados por categoria de evento.
# Compatibilidade: K_INTERNAL_URL (legado) e fallback quando o destino especifico
# nao esta configurado.
K_INTERNAL_URL = "internal_url"  # legacy fallback (catch-all)
K_INTERNAL_URL_SCHEDULING = "internal_url_scheduling"  # eventos de agendamento
K_INTERNAL_URL_PAYOUT = "internal_url_payout"  # status de payouts PIX (pixkey, qrcode)
K_INTERNAL_URL_CHARGE = "internal_url_charge"  # status de cobrancas PIX recebidas (charge)

INTERNAL_URL_TARGETS = ("default", "scheduling", "payout", "charge")
_INTERNAL_URL_KEY_BY_TARGET = {
    "default": K_INTERNAL_URL,
    "scheduling": K_INTERNAL_URL_SCHEDULING,
    "payout": K_INTERNAL_URL_PAYOUT,
    "charge": K_INTERNAL_URL_CHARGE,
}


def internal_url_key(target: str) -> str:
    """Resolve um target ('scheduling' | 'payout' | 'charge' | 'default') ao K_* key."""
    try:
        return _INTERNAL_URL_KEY_BY_TARGET[target]
    except KeyError as e:
        raise ValueError(f"invalid_internal_url_target: {target}") from e


async def get(db: AsyncSession, key: str) -> str | None:
    row = await db.get(ConfigKV, key)
    return row.value if row else None


async def set_(db: AsyncSession, key: str, value: str | None) -> None:
    row = await db.get(ConfigKV, key)
    if row is None:
        row = ConfigKV(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    await db.flush()


async def delete(db: AsyncSession, key: str) -> None:
    row = await db.get(ConfigKV, key)
    if row is not None:
        await db.delete(row)
        await db.flush()


async def get_webhook_secret(db: AsyncSession) -> str | None:
    """Retorna o webhook secret (HMAC) do config store, se configurado."""
    return await get(db, K_ASAAS_WEBHOOK_SECRET)


# ── Bootstrap via env ────────────────────────────────────────────────────────
# Mapeia env var (Settings field) -> chave do asaas.config. Mantemos o nome
# da chave do DB intacto (`asaas_api_key`, etc) — a env var apenas hidrata
# valor inicial. Operador pode override via POST /config/key e o DB vence.
_ENV_BOOTSTRAP = (
    # (settings_field, db_key)
    ("asaas_api_key", K_ASAAS_API_KEY),
    ("asaas_external_url", K_EXTERNAL_URL),
    ("asaas_wallet_id", K_ASAAS_WALLET_ID),
    ("asaas_internal_url", K_INTERNAL_URL),
    ("asaas_internal_url_charge", K_INTERNAL_URL_CHARGE),
    ("asaas_internal_url_payout", K_INTERNAL_URL_PAYOUT),
    ("asaas_internal_url_scheduling", K_INTERNAL_URL_SCHEDULING),
    ("asaas_webhook_secret", K_ASAAS_WEBHOOK_SECRET),
    ("asaas_security_token", K_ASAAS_SECURITY_TOKEN),
)


async def seed_from_env(db: AsyncSession) -> dict[str, str]:
    """Pos-wipe / first-boot: popula asaas.config a partir do .env.

    Chamada no lifespan startup. Para cada chave do _ENV_BOOTSTRAP:
      - Se o DB ja tem valor (truthy), mantemos — operador venceu via API.
      - Se o DB esta vazio/null E a env var tem valor, copia env -> DB.

    Retorna dict {db_key: 'seeded' | 'kept'} pra log/audit.
    """
    settings = get_settings()
    result: dict[str, str] = {}
    for settings_field, db_key in _ENV_BOOTSTRAP:
        env_value = getattr(settings, settings_field, None)
        current = await get(db, db_key)
        if current:
            result[db_key] = "kept"
            continue
        if env_value:
            await set_(db, db_key, env_value)
            result[db_key] = "seeded"
        else:
            result[db_key] = "absent"
    return result


async def all_status(db: AsyncSession) -> dict:
    """Short summary of what is configured (without leaking secrets)."""

    def mask(v: str | None) -> str | None:
        if not v:
            return None
        if len(v) <= 10:
            return "***"
        return f"{v[:6]}...{v[-4:]}"

    return {
        "external_url": await get(db, K_EXTERNAL_URL),
        "internal_url": await get(db, K_INTERNAL_URL),
        "internal_url_scheduling": await get(db, K_INTERNAL_URL_SCHEDULING),
        "internal_url_payout": await get(db, K_INTERNAL_URL_PAYOUT),
        "internal_url_charge": await get(db, K_INTERNAL_URL_CHARGE),
        "asaas_api_key": mask(await get(db, K_ASAAS_API_KEY)),
        "asaas_security_token": mask(await get(db, K_ASAAS_SECURITY_TOKEN)),
        "asaas_webhook_secret": mask(await get(db, K_ASAAS_WEBHOOK_SECRET)),
        "asaas_wallet_id": await get(db, K_ASAAS_WALLET_ID),
        "asaas_account_name": await get(db, K_ASAAS_ACCOUNT_NAME),
    }
