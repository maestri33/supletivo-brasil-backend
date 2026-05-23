import time

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.models import Lead

_jwks_cache: dict | None = None
_jwks_cached_at: float = 0.0


async def get_jwks():
    global _jwks_cache, _jwks_cached_at
    if _jwks_cache is not None and time.monotonic() - _jwks_cached_at < 300:
        return _jwks_cache
    async with httpx.AsyncClient(base_url=settings.JWT_BASE_URL) as client:
        resp = await client.get("/.well-known/jwks.json")
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cached_at = time.monotonic()
        return _jwks_cache


async def get_current_external_id(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> str:
    token = credentials.credentials
    jwks = await get_jwks()

    if not jwks.get("keys"):
        raise HTTPException(401, "Nenhuma chave no JWKS")

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
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Token invalido: {exc}")

    if "lead" not in payload.get("roles", []):
        raise HTTPException(403, "Requires 'lead' role")

    return payload["external_id"]


def _require_status(required: str):
    async def check_status(
        external_id: str = Depends(get_current_external_id),
    ) -> str:
        lead = await Lead.get_or_none(external_id=external_id)
        if not lead:
            raise HTTPException(404, "Lead nao encontrado")
        if lead.status != required:
            raise HTTPException(403, f"Status '{lead.status}' — requer '{required}'")
        return external_id

    return Depends(check_status)


def require_captured():
    return _require_status("captured")


def require_personal():
    return _require_status("personal")


def require_education():
    return _require_status("education")


def require_birth():
    return _require_status("birth")


def require_address():
    return _require_status("address")


def require_waiting():
    return _require_status("waiting")


def require_checkout():
    return _require_status("checkout")


def require_completed():
    return _require_status("completed")
