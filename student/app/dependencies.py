"""Dependencies — validacao JWT/JWKS com gate por role."""

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
    async with httpx.AsyncClient(base_url=settings.jwt_base_url) as client:
        resp = await client.get("/.well-known/jwks.json")
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cached_at = time.monotonic()
        return _jwks_cache


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> dict:
    """Valida o JWT RS256 contra a JWKS do servico jwt e devolve o payload."""
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
        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"require": ["exp", "roles", "external_id"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(401, "Token expired") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Invalid token: {exc}") from exc


def require_role(role: str):
    """Gate por role. Devolve o external_id do token quando a role confere."""

    async def _check(payload: dict = Depends(get_token_payload)) -> UUID:
        if role not in payload.get("roles", []):
            raise HTTPException(403, f"Requires '{role}' role")
        return UUID(payload["external_id"])

    return Depends(_check)
