"""Dependencies — validacao JWT/JWKS e gates por papel (CONVENTION §5).

Decisao de papel para os endpoints do training:
- `role_trainee` (default: "training") — quem envia submissao / consulta progresso.
  E' o papel atribuido pelo `candidate/services/selfie.py` ao concluir o funil.
- `role_coordinator` (default: "coordinator") — quem aprova/rejeita entrevista.

Espelha o padrao de validacao JWT do `candidate/app/dependencies.py` (JWKS
cacheado por 5 min, RS256, claims `external_id` + `roles`).
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
_bearer = HTTPBearer()


async def get_jwks() -> dict:
    """JWKS em cache por 5 min — evita N requests por validacao."""
    global _jwks_cache, _jwks_cached_at
    if _jwks_cache is not None and time.monotonic() - _jwks_cached_at < 300:
        return _jwks_cache
    async with httpx.AsyncClient(
        base_url=settings.jwt_base_url, timeout=settings.http_timeout
    ) as client:
        resp = await client.get("/.well-known/jwks.json")
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cached_at = time.monotonic()
        return _jwks_cache


async def _decode_token(token: str) -> dict:
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
        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"require": ["exp", "roles", "external_id"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(401, "Token expirado") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Token invalido: {exc}") from exc


async def get_current_payload(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    return await _decode_token(credentials.credentials)


def _require_role(*allowed_roles: str):
    """Factory de gate: pelo menos UM dos papeis dados precisa estar no JWT."""
    allowed = set(allowed_roles)

    async def _check(payload: dict = Depends(get_current_payload)) -> UUID:
        roles = set(payload.get("roles") or [])
        if not (allowed & roles):
            raise HTTPException(
                403,
                f"Requer papel em {sorted(allowed)} — token tem {sorted(roles)}",
            )
        return UUID(payload["external_id"])

    return _check


def require_trainee():
    """Endpoint do trainee — quem ja concluiu o candidate e esta na trilha."""
    return Depends(_require_role(settings.role_trainee))


def require_coordinator():
    """Endpoint do coordenador do hub — aprova/rejeita entrevista."""
    return Depends(_require_role(settings.role_coordinator))
