"""Aggregated health check + balance + webhook status."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .. import config_store as cfg
from ..config import get_settings
from ..integrations.asaas_client import AsaasClient, AsaasError

_settings = get_settings()


def status(db: Session) -> dict:
    out: dict[str, Any] = {
        "configured": cfg.all_status(db),
        "account": None,
        "balance": None,
        "webhook_registered": None,
        "errors": [],
    }

    api_key = cfg.get(db, cfg.K_ASAAS_API_KEY)
    if not api_key:
        out["errors"].append("asaas_api_key_not_set")
        return out

    client = AsaasClient(api_key)
    try:
        try:
            out["account"] = client.get_my_account()
        except AsaasError as e:
            out["errors"].append(f"myAccount_failed:{e.status_code}")
        try:
            out["balance"] = client.get_balance()
        except AsaasError as e:
            out["errors"].append(f"balance_failed:{e.status_code}")
        try:
            hooks = client.list_webhooks()
            external_url = cfg.get(db, cfg.K_EXTERNAL_URL)
            webhook_url = f"{external_url.rstrip('/')}/webhook/" if external_url else None
            for w in hooks.get("data") or []:
                if w.get("name") == _settings.webhook_name or w.get("url") == webhook_url:
                    out["webhook_registered"] = w
                    break
            if not out["webhook_registered"]:
                out["errors"].append("webhook_not_registered")
        except AsaasError as e:
            out["errors"].append(f"list_webhooks_failed:{e.status_code}")
    finally:
        client.close()

    return out
