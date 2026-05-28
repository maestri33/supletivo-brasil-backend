"""Auth guard — validacao JWT via JWKS do proprio servico jwt.

Usado para proteger endpoints internos do auth service (atomic, log).
O token e' validado contra as chaves JWKS publicadas pelo servico jwt.
"""

import time
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

settings = get_settings()

_jwks_cache: dict | None = None
_jwks_cached_at: float = 0.0

_bearer_scheme = HTTPBearer()


async def _get_jwks() -> dict:
    """Cache JWKS por 5 min."""
    global _jwks_cache, _jwks_cached_at
    if _jwks_cache is not None and time.monotonic() - _jwks_cached_at < 300:
        return _jwks_cache  # type: ignore[return-value]
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.JWT_SERVICE_URL}/.well-known/jwks.json", timeout=5)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_cached_at = time.monotonic()
            return _jwks_cache  # type: ignore[return-value]
    except Exception as exc:
        logger.error("jwks_fetch_failed", error=type(exc).__name__)
        raise HTTPException(502, "Falha ao carregar chaves JWKS") from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """Valida JWT e retorna o payload completo.

    Levanta 401 se o token for invalido ou expirado.
    """
    token = credentials.credentials
    jwks = await _get_jwks()

    if not jwks.get("keys"):
        logger.error("jwks_no_keys")
        raise HTTPException(500, "Nenhuma chave no JWKS")

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
        raise HTTPException(401, "Token expirado") from exc
    except jwt.PyJWTError as exc:
        logger.warning("jwt_validation_failed", error=type(exc).__name__)
        raise HTTPException(401, "Token invalido") from exc

    return payload


async def require_admin(
    payload: dict = Depends(get_current_user),
) -> dict:
    """Exige papel 'admin' no JWT."""
    roles = payload.get("roles", [])
    if "admin" not in roles:
        raise HTTPException(403, "Requer papel 'admin'")
    return payload


async def get_current_external_id(
    payload: dict = Depends(get_current_user),
) -> UUID:
    """Retorna o external_id do usuario autenticado."""
    return UUID(payload["external_id"])
