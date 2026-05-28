"""Webhook hardening: HMAC signature + IP allow-list para InfinitePay.

InfinitePay pode enviar o header `x-infinitepay-signature` com HMAC-SHA256
do body bruto. A chave secreta (`infinitepay_webhook_secret`) e configurada
no painel InfinitePay e replicada no nosso config store (ou .env via
INFINITEPAY_WEBHOOK_SECRET).

IP allow-list: restringe os endpoints de webhook a faixas CIDR conhecidas
da InfinitePay. A lista e configurada via env (INFINITEPAY_WEBHOOK_ALLOWED_CIDRS)
e pode ser ampliada pelo operador.

Defesa em profundidade: IP allow-list (camada 1) + HMAC signature (camada 2).
Ambas sao aplicadas como dependencias FastAPI nas rotas publicas de webhook.

Padrao segue o modulo asaas/app/services/webhook_security.py para consistencia
cross-service (SecSection 12: 1 integracao externa = 1 app dono).
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os

from fastapi import Header, HTTPException, Request

from ..utils.logging import log_event

_HEADER = "x-infinitepay-signature"

# CIDRs padrao da InfinitePay (producao). Mantenha atualizado.
# InfinitePay usa Cloudflare como proxy reverso nos dominios publicos
# (api.checkout.infinitepay.io, recibo.infinitepay.io), mas os webhooks
# server-to-server partem dos servidores de origem deles — nao da Cloudflare.
#
# Como descobrir os IPs de origem:
#  1. Consulte a doc oficial: https://docs.infinitepay.io
#  2. Verifique o header X-Forwarded-For nos webhooks reais em staging
#  3. Contate o suporte InfinitePay para confirmar as faixas CIDR oficiais
#
# Ate la, a lista fica vazia — em producao isso BLOQUEIA todos os webhooks
# (fail-closed), forcando o operador a configurar antes do go-live.
_INFINITEPAY_DEFAULT_CIDRS: tuple[str, ...] = (
    # Preencher com as faixas CIDR oficiais da InfinitePay.
)

# Fallback amplo — sandbox/dev. Remover em producao configurando
# INFINITEPAY_WEBHOOK_ALLOWED_CIDRS explicitamente.
_INFINITEPAY_DEV_CIDRS: tuple[str, ...] = (
    "0.0.0.0/0",  # dev: accept all
)

# Sentinel para detectar "nao configurado" vs "desabilitado explicitamente".
_UNSET = "\N{EM DASH}"


def _client_ip(request: Request) -> str | None:
    """IP real do cliente (X-Forwarded-For aware)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else None


# ── IP allow-list ──────────────────────────────────────────────────────────


def _allowed_cidrs() -> list[str]:
    raw = os.getenv("INFINITEPAY_WEBHOOK_ALLOWED_CIDRS", "")
    if raw:
        return [c.strip() for c in raw.split(",") if c.strip()]
    env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development"))
    if env in ("development", "dev", "staging"):
        return list(_INFINITEPAY_DEV_CIDRS)
    return list(_INFINITEPAY_DEFAULT_CIDRS)


def _ip_allowed(client_ip: str | None) -> bool:
    """True se o IP de origem esta em pelo menos uma faixa CIDR permitida."""
    if not client_ip:
        return False
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for cidr_s in _allowed_cidrs():
        try:
            net = ipaddress.ip_network(cidr_s, strict=False)
        except ValueError:
            continue
        if addr in net:
            return True
    return False


async def verify_ip_allowlist(request: Request) -> None:
    """FastAPI dependency: rejeita IPs fora da allow-list InfinitePay.

    Quando INFINITEPAY_WEBHOOK_ALLOWED_CIDRS nao esta configurada:
    - Em dev/staging: aceita todos (0.0.0.0/0).
    - Em producao: usa defaults (se vazios, BLOQUEIA — forcando o operador
      a configurar as faixas antes de ir pra prod).

    Para desabilitar explicitamente (dev local), defina como vazia
    a env INFINITEPAY_WEBHOOK_ALLOWED_CIDRS="" (nunca em producao).
    """
    raw = os.getenv("INFINITEPAY_WEBHOOK_ALLOWED_CIDRS", _UNSET)
    if raw == "":
        return  # explicitly disabled — allow all (dev/testing only)

    ip = _client_ip(request)
    if not _ip_allowed(ip):
        raise HTTPException(status_code=403, detail="ip_not_allowed")


# ── HMAC signature verification ────────────────────────────────────────────


def _get_webhook_secret() -> str | None:
    """Busca o webhook secret do env (leitura em runtime — sem cache)."""
    return os.getenv("INFINITEPAY_WEBHOOK_SECRET") or None


def _verify_signature(body: bytes, secret: str, signature: str) -> bool:
    """Comparacao em tempo constante via hmac.compare_digest."""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def verify_hmac(
    request: Request,
    infinitepay_signature: str | None = Header(default=None, alias=_HEADER),
) -> None:
    """FastAPI dependency: valida HMAC-SHA256 do body contra o webhook secret.

    Quando nao ha secret configurado (primeiro boot / ambiente de dev),
    aceita sem validar. Em producao o secret DEVE ser configurado.

    Levanta HTTP 401 se a assinatura for invalida.
    """
    secret = _get_webhook_secret()
    if not secret:
        # Sem secret = webhook signature mode not configured.
        # Allow through so IP allow-list still applies (defense in depth).
        env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development"))
        if env not in ("development", "dev", "staging"):
            log_event("webhook_hmac_disabled", env=env, service="infinitepay", severity="WARNING")
        return

    body = await request.body()
    if not _verify_signature(body, secret, infinitepay_signature or ""):
        log_event("webhook_hmac_rejected", service="infinitepay")
        raise HTTPException(status_code=401, detail="invalid_signature")


# ── Health check helper ────────────────────────────────────────────────────


def webhook_security_status() -> dict:
    """Retorna status detalhado da configuracao de seguranca do webhook.

    Usado pelo health check para expor ao monitoring/dashboard, permitindo
    alertas quando o webhook estiver inseguro em producao.

    Campos:
    - webhook_hmac_configured: True se INFINITEPAY_WEBHOOK_SECRET esta definido.
    - webhook_ip_allowlist_configured: True se ha CIDRs configurados (nao vazio/0.0.0.0/0).
    - webhook_ip_allowlist_custom: True se CIDRs foram definidos pelo operador
      (nao e o default dev 0.0.0.0/0 nem o sentinel _UNSET).
    """
    raw = os.getenv("INFINITEPAY_WEBHOOK_ALLOWED_CIDRS", _UNSET)

    hmac_configured = bool(_get_webhook_secret())
    ip_configured = False
    ip_custom = False

    if raw != _UNSET and raw.strip():
        cidrs = [c.strip() for c in raw.split(",") if c.strip()]
        if cidrs and cidrs != ["0.0.0.0/0"]:
            ip_configured = True
            ip_custom = True

    return {
        "webhook_hmac_configured": hmac_configured,
        "webhook_ip_allowlist_configured": ip_configured,
        "webhook_ip_allowlist_custom": ip_custom,
    }


def webhook_security_configured() -> bool:
    """True se a seguranca do webhook esta adequadamente configurada.

    Retorna False quando:
    - Em producao sem nenhum CIDR configurado (gap de seguranca).
    - Em producao com CIDR amplo demais (0.0.0.0/0).
    - Em producao com secret HMAC nao configurado.

    Retorna True quando:
    - CIDRs especificos + secret HMAC estao configurados (seguro).
    - Em dev/staging (0.0.0.0/0 e aceitavel).
    """
    raw = os.getenv("INFINITEPAY_WEBHOOK_ALLOWED_CIDRS", _UNSET)

    env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development"))
    if env in ("development", "dev", "staging"):
        return True  # dev/staging: aceitavel

    # Producao: exige CIDRs explicitos + secret HMAC.
    if raw == _UNSET or not raw.strip():
        return False
    cidrs = [c.strip() for c in raw.split(",") if c.strip()]
    if not cidrs or cidrs == ["0.0.0.0/0"]:
        return False

    # HMAC secret deve estar configurado em producao.
    if not _get_webhook_secret():
        return False

    return True
