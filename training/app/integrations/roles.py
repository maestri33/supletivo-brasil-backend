"""Integracao com o servico `roles` (dono dos papeis do usuario, CONVENTION §7/§8).

Usado pelo `services/promotion.py` quando o coordenador aprova o trainee:
POST /api/v1/role/{external_id}/up/{to_role}  → promove para `promoter`.
"""

import httpx

from app.config import get_settings
from app.integrations import BaseClient, request_with_retry


class RolesClient(BaseClient):
    async def promote(self, external_id: str, to_role: str) -> dict:
        resp = await request_with_retry(
            self.client, "POST", f"/api/v1/role/{external_id}/up/{to_role}"
        )
        return resp.json()


def roles_http_client() -> httpx.AsyncClient:
    s = get_settings()
    return httpx.AsyncClient(base_url=s.roles_base_url, timeout=s.http_timeout)
