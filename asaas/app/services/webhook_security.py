"""Webhook hardening: HMAC signature + IP allow-list.

Asaas envia o header `asaas-signature` com HMAC-SHA256 do body bruto.
A chave secreta (`asaas_webhook_secret`) e configurada no painel Asaas
e replicada no nosso config store (ou .env via K_ASAAS_WEBHOOK_SECRET).

IP allow-list: restringe os endpoints de webhook a faixas CIDR conhecidas
do Asaas. A lista e configurada via env (ASAAS_WEBHOOK_ALLOWED_CIDRS) e
pode ser ampliada pelo operador.

Integracao (§15): as dependencias abaixo sao chamadas nas rotas publicas
/webhook/ e /security-validator.  Nao afetam rotas internas.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os

from fastapi import Header, HTTPException, Request

from .. import config_store as cfg
from ..utils.logging import log_event

_HEADER = "asaas-signature"

# CIDRs padrao do Asaas (producao + sandbox). Mantenha atualizado.
# Ref: https://docs.asaas.com/docs/webhooks#ip-de-origem
_ASAAS_DEFAULT_CIDRS = (
    "52.67.135.115/32",
    "18.231.44.29/32",
    "18.229.238.53/32",
    "54.233.218.242/32",
    # sandbox
    "52.67.0.0/24",
)


def _allowed_cidrs() -> list[str]:
    raw = os.getenv("ASAAS_WEBHOOK_ALLOWED_CIDRS", "")
    if raw:
        return [c.strip() for c in raw.split(",") if c.strip()]
    return list(_ASAAS_DEFAULT_CIDRS)


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


async def _get_webhook_secret(db) -> str | None:
    """Busca o webhook secret do config store; fallback ao env."""
    secret = await cfg.get_webhook_secret(db)
    if secret:
        return secret
    return os.getenv("ASAAS_WEBHOOK_SECRET") or None


def _verify_signature(body: bytes, secret: str, signature: str) -> bool:
    """Comparacao em tempo constante via hmac.compare_digest."""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def verify_hmac(
    request: Request,
    db,
    asaas_signature: str | None = Header(default=None, alias=_HEADER),
) -> None:
    """FastAPI dependency: valida HMAC-SHA256 do body contra o webhook secret.

    Quando nao ha secret configurado (primeiro boot / ambiente de dev),
    aceita sem validar. Em producao o secret DEVE ser configurado.

    Levanta HTTP 401 se a assinatura for invalida.
    """
    secret = await _get_webhook_secret(db)
    if not secret:
        # Sem secret = webhook mode not configured. Allow through so the
        # existing asaas_access_token check still applies (defense in depth).
        return

    body = await request.body()
    if not _verify_signature(body, secret, asaas_signature or ""):
        log_event("webhook_hmac_rejected")
        raise HTTPException(status_code=401, detail="invalid_signature")


async def verify_ip_allowlist(request: Request) -> None:
    """FastAPI dependency: rejeita IPs fora da allow-list Asaas.

    Quando ASAAS_WEBHOOK_ALLOWED_CIDRS nao esta configurada, usa os defaults
    de producao. Para desabilitar (dev local), defina como vazia.
    """
    raw = os.getenv("ASAAS_WEBHOOK_ALLOWED_CIDRS", "\N{EM DASH}")
    if raw == "":
        # Explicitly disabled — allow all (dev/testing).
        return

    ip = request.client.host if request.client else None
    if not _ip_allowed(ip):
        log_event("webhook_ip_rejected", ip=ip)
        raise HTTPException(status_code=403, detail="ip_not_allowed")
