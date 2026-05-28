"""Dependencies — validacao JWT/JWKS + gate de role admin/staff.

Espelha `lead/app/dependencies.py`, trocando a checagem de role `"lead"`
por interseccao contra `settings.STAFF_ROLES` (admin, staff).
"""

import time
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

settings = get_settings()

_jwks_cache: dict | None = None
_jwks_cached_at: float = 0.0


async def get_jwks() -> dict:
    """Cache JWKS por 5 min — evita N requests por validacao."""
    global _jwks_cache, _jwks_cached_at
    if _jwks_cache is not None and time.monotonic() - _jwks_cached_at < 300:
        return _jwks_cache
    try:
        async with httpx.AsyncClient(base_url=settings.JWT_BASE_URL) as client:
            resp = await client.get("/.well-known/jwks.json")
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_cached_at = time.monotonic()
            return _jwks_cache
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"JWKS unreachable: {exc}") from exc


async def get_current_external_id(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> UUID:
    """Valida JWT RS256, exige `exp`/`roles`/`external_id`, e checa role ∈ STAFF_ROLES."""
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

    user_roles = payload.get("roles", [])
    if not any(role in user_roles for role in settings.STAFF_ROLES):
        raise HTTPException(403, f"Requires one of: {settings.STAFF_ROLES}")

    return UUID(payload["external_id"])
