"""config/key: onboard an Asaas production API key.

Flow broken into two steps so the user can react:

  set_key(api_key):
    - ping /v3/myAccount to prove the key is valid and production
    - generate a random security token for the "Mecanismo de Seguranca"
    - persist api_key + token (pending/commit-on-confirm semantics handled at call sites)
    - return an instructions block the client will display: where in painel to paste the
      token, which URL to use as security validator, and which webhook endpoint will
      be registered in the next step

  confirm_key():
    - register the managed webhook on Asaas pointing at <external_url>/webhook/
    - keep api_key/security_token intact on webhook failure so the user can retry
"""

from __future__ import annotations

import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from .. import config_store as cfg
from ..config import WEBHOOK_EVENTS, get_settings
from ..exceptions import ValidationError
from ..integrations.asaas_client import AsaasClient, AsaasError

_settings = get_settings()


def webhook_url(external_url: str) -> str:
    return f"{external_url.rstrip('/')}/webhook/"


# ---------- step 1: set_key ----------


async def set_key(db: AsyncSession, api_key: str) -> dict:
    is_prod = api_key.startswith("$aact_prod_")
    is_sandbox = api_key.startswith("$aact_hmlg_")
    if not is_prod and not (is_sandbox and _settings.asaas_allow_sandbox):
        # Production-only por padrao; sandbox so com ASAAS_ALLOW_SANDBOX=true
        raise ValidationError("production_key_required")

    async with AsaasClient(api_key) as client:
        try:
            account = await client.get_my_account()
        except AsaasError as e:
            raise ValidationError(f"asaas_rejected_key: {e.body}") from e

    # preserva token ja existente pra sobreviver a rollbacks sem refazer painel
    token = await cfg.get(db, cfg.K_ASAAS_SECURITY_TOKEN) or secrets.token_hex(32)

    await cfg.set_(db, cfg.K_ASAAS_API_KEY, api_key)
    await cfg.set_(db, cfg.K_ASAAS_SECURITY_TOKEN, token)
    await cfg.set_(db, cfg.K_ASAAS_WALLET_ID, account.get("walletId") or account.get("id") or "")
    await cfg.set_(
        db, cfg.K_ASAAS_ACCOUNT_NAME, account.get("name") or account.get("companyName") or ""
    )

    return {
        "security_token": token,
        "account": {
            "name": account.get("name") or account.get("companyName"),
            "email": account.get("email"),
            "walletId": account.get("walletId") or account.get("id"),
        },
    }


# ---------- step 2: confirm_key ----------


async def _find_managed_webhook(client: AsaasClient, wanted_url: str) -> dict | None:
    try:
        res = await client.list_webhooks()
    except AsaasError:
        return None
    for w in res.get("data") or []:
        if w.get("name") == _settings.webhook_name or w.get("url") == wanted_url:
            return w
    return None


async def _register_webhook(client: AsaasClient, external_url: str, auth_token: str) -> dict:
    # Sempre recria pra garantir authToken sincronizado com nosso DB
    target_url = webhook_url(external_url)
    existing = await _find_managed_webhook(client, target_url)
    if existing:
        try:
            await client.delete_webhook(existing["id"])
        except AsaasError:
            pass
    # Asaas exige email nao-vazio; pega o da conta autenticada
    account = await client.get_my_account()
    notify_email = account.get("email") or "webhook@invalid.local"
    payload = {
        "name": _settings.webhook_name,
        "url": target_url,
        "email": notify_email,
        "enabled": True,
        "interrupted": False,
        "apiVersion": 3,
        "authToken": auth_token,
        "sendType": "SEQUENTIALLY",
        "events": WEBHOOK_EVENTS,
    }
    return await client.create_webhook(payload)


def _doc_matches(masked_or_full: str, expected: str) -> bool:
    """Asaas masks CPF as ***.XXX.XXX-** but returns CNPJ unmasked.
    We accept if every non-* character matches the expected digit in the same slot."""
    a = "".join(ch for ch in masked_or_full if ch.isdigit() or ch == "*")
    b = "".join(ch for ch in expected if ch.isdigit())
    if len(a) == 0 or len(b) == 0:
        return False
    # Align by length — masked CPF has same length (11) after stripping
    if len(a) != len(b):
        return False
    for x, y in zip(a, b, strict=True):
        if x == "*":
            continue
        if x != y:
            return False
    return True


async def confirm_key(db: AsyncSession) -> dict:
    """Apos set_key + configuracao do painel pelo usuario, registra o webhook.

    A validacao de chave PIX ficou no modulo /pixkey — o confirm aqui so garante
    que o webhook da conta aponta pra gente com o authToken atual.
    """
    api_key = await cfg.get(db, cfg.K_ASAAS_API_KEY)
    token = await cfg.get(db, cfg.K_ASAAS_SECURITY_TOKEN)
    external_url = await cfg.get(db, cfg.K_EXTERNAL_URL)
    if not api_key or not token:
        raise ValidationError("set_key_not_done")
    if not external_url:
        raise ValidationError("external_url_not_set")

    # nao limpa secrets em falha — usuario pode retry so do webhook
    async with AsaasClient(api_key) as client:
        webhook = await _register_webhook(client, external_url, token)
        return {"webhook_registered": webhook}
