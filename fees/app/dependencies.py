"""Dependencies FastAPI — validação JWT (gate de coordenador) e clients.

Auth espelha `lead/app/dependencies.py`: busca o JWKS do serviço `jwt`, valida o
token RS256 e exige a role de coordenador. Só o coordenador do polo opera taxas.
"""

import time
from collections.abc import AsyncIterator
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.integrations.asaas import AsaasClient

settings = get_settings()

_jwks_cache: dict | None = None
_jwks_cached_at: float = 0.0


async def get_jwks() -> dict:
    """Cache do JWKS por 5 min — evita um request por validação."""
    global _jwks_cache, _jwks_cached_at
    if _jwks_cache is not None and time.monotonic() - _jwks_cached_at < 300:
        return _jwks_cache
    async with httpx.AsyncClient(base_url=settings.jwt_base_url) as client:
        resp = await client.get("/.well-known/jwks.json")
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cached_at = time.monotonic()
        return _jwks_cache


async def get_current_coordinator(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> UUID:
    """Valida o JWT e exige a role de coordenador. Retorna o external_id dele."""
    token = credentials.credentials
    jwks = await get_jwks()
    if not jwks.get("keys"):
        raise HTTPException(401, "No keys in JWKS")

    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    key_data = next(
        (k for k in jwks["keys"] if kid and k.get("kid") == kid),
        jwks["keys"][0],
    )
    public_key = jwt.PyJWK(key_data).key

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"require": ["exp", "roles", "external_id"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(401, "Token expired") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Invalid token: {exc}") from exc

    if settings.coordinator_role not in payload.get("roles", []):
        raise HTTPException(403, f"Requires '{settings.coordinator_role}' role")

    return UUID(payload["external_id"])


async def get_asaas_client() -> AsyncIterator[AsaasClient]:
    """Client do serviço `asaas` por request (httpx.AsyncClient gerenciado)."""
    async with httpx.AsyncClient(
        base_url=settings.asaas_base_url, timeout=settings.http_timeout
    ) as http:
        yield AsaasClient(http)
