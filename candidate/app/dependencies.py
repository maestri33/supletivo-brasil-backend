"""Dependencies — validacao JWT/JWKS e gates por status do Candidate.

O JWT carrega o papel `lead`: durante todo o funil o usuario ainda e' um lead
(aspirante); so' na conclusao e' promovido a `training`. Por isso o gate de
papel aqui e' `lead` — e' intencional, nao um residuo do servico de origem.
"""

import time
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import Candidate, CandidateStatus

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

    if "lead" not in payload.get("roles", []):
        raise HTTPException(403, "Requer papel 'lead'")

    return UUID(payload["external_id"])


def _require_status(*required: CandidateStatus):
    """Gate por status do Candidate. Aceita um ou mais status validos."""
    allowed = {s.value for s in required}

    async def check_status(
        external_id: UUID = Depends(get_current_external_id),
        session: AsyncSession = Depends(get_session),
    ) -> UUID:
        candidate = await session.scalar(
            select(Candidate).where(Candidate.external_id == str(external_id))
        )
        if not candidate:
            raise HTTPException(404, "Candidato nao encontrado")
        if candidate.status not in allowed:
            expected = " ou ".join(s.value for s in required)
            raise HTTPException(403, f"Status '{candidate.status}' — requer '{expected}'")
        return external_id

    return Depends(check_status)


def require_captured():
    return _require_status(CandidateStatus.CAPTURED)


def require_personal():
    return _require_status(CandidateStatus.PERSONAL)


def require_education():
    return _require_status(CandidateStatus.EDUCATION)


def require_birth():
    return _require_status(CandidateStatus.BIRTH)


def require_address():
    return _require_status(CandidateStatus.ADDRESS)


def require_documents():
    return _require_status(CandidateStatus.DOCUMENTS)


def require_pixkey():
    return _require_status(CandidateStatus.PIXKEY)


def require_selfie():
    return _require_status(CandidateStatus.SELFIE)
