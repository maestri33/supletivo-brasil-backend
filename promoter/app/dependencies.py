"""Dependencies — validacao JWT/JWKS e gate de promoter ativo.

O JWT do promoter carrega o papel `promoter` (concedido pelo `roles` na criacao).
As rotas autenticadas exigem esse papel e um registro de promoter ATIVO.
"""

import time
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import Promoter, PromoterStatus
from app.services import promoter as promoter_svc

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


async def get_current_external_id(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> UUID:
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
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(401, "Token expirado") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Token invalido: {exc}") from exc

    if "promoter" not in payload.get("roles", []):
        raise HTTPException(403, "Requer papel 'promoter'")

    return UUID(payload["external_id"])


async def get_current_promoter(
    external_id: UUID = Depends(get_current_external_id),
    session: AsyncSession = Depends(get_session),
) -> Promoter:
    """Carrega o promoter autenticado e exige status ativo."""
    promoter = await promoter_svc.get(session, external_id)
    if not promoter:
        raise HTTPException(404, "Promotor nao encontrado")
    if promoter.status != PromoterStatus.ACTIVE.value:
        raise HTTPException(403, f"Promotor '{promoter.status}' — requer 'active'")
    return promoter
