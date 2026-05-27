"""Aggregated health check + balance + webhook status."""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .. import config_store as cfg
from ..config import get_settings
from ..integrations.asaas_client import AsaasClient, AsaasError

_settings = get_settings()


async def status(db: AsyncSession) -> dict:
    secret = await cfg.get_webhook_secret(db)
    out: dict[str, Any] = {
        "configured": await cfg.all_status(db),
        "account": None,
        "balance": None,
        "webhook_registered": None,
        "webhook_hmac_configured": bool(secret),
        "errors": [],
    }

    api_key = await cfg.get(db, cfg.K_ASAAS_API_KEY)
    if not api_key:
        out["errors"].append("asaas_api_key_not_set")
        return out

    if not secret:
        env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development"))
        if env not in ("development", "dev", "staging"):
            out["errors"].append("webhook_hmac_disabled")

    async with AsaasClient(api_key) as client:
        try:
            out["account"] = await client.get_my_account()
        except AsaasError as e:
            out["errors"].append(f"myAccount_failed:{e.status_code}")
        try:
            out["balance"] = await client.get_balance()
        except AsaasError as e:
            out["errors"].append(f"balance_failed:{e.status_code}")
        try:
            hooks = await client.list_webhooks()
            external_url = await cfg.get(db, cfg.K_EXTERNAL_URL)
            webhook_url = f"{external_url.rstrip('/')}/webhook/" if external_url else None
            for w in hooks.get("data") or []:
                if w.get("name") == _settings.webhook_name or w.get("url") == webhook_url:
                    out["webhook_registered"] = w
                    break
            if not out["webhook_registered"]:
                out["errors"].append("webhook_not_registered")
        except AsaasError as e:
            out["errors"].append(f"list_webhooks_failed:{e.status_code}")

    return out
