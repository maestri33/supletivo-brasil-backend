"""Dependências FastAPI — validação JWT (RS256 + JWKS) e gates por status.

JWT do matriculando carrega o papel `enrollment` (promovido pelo webhook
lead.completed → roles.promote). O coordenador carrega `coordinator`. Ambos
emitidos pelo serviço `jwt`.

Gates:
  - require_status(<EnrollmentStatus>) — só avança quem está exatamente
    naquele status (idempotente, sem pular etapa).
  - require_coordinator() — gate de role `coordinator` para o endpoint de
    liberação (CONVENTION §8: roles vêm do JWT, não do DB local).
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
from app.models import EnrollmentStatus
from app.services import enrollment as enrollment_svc

settings = get_settings()

_jwks_cache: dict | None = None
_jwks_cached_at: float = 0.0


async def get_jwks() -> dict:
    """Cache JWKS por 5 min — evita N requests por validação."""
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


async def _decoded_jwt(credentials: HTTPAuthorizationCredentials) -> dict:
    """Decodifica e valida o JWT contra o JWKS do app `jwt`."""
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
        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"require": ["exp", "roles", "external_id"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(401, "Token expirado") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Token inválido: {exc}") from exc


async def get_current_external_id(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> UUID:
    """Matriculando autenticado — exige role `enrollment` no JWT."""
    payload = await _decoded_jwt(credentials)
    if "enrollment" not in payload.get("roles", []):
        raise HTTPException(403, "Requer papel 'enrollment'")
    return UUID(payload["external_id"])


async def get_current_coordinator(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> UUID:
    """Coordenador autenticado — exige role `coordinator` no JWT."""
    payload = await _decoded_jwt(credentials)
    if "coordinator" not in payload.get("roles", []):
        raise HTTPException(403, "Requer papel 'coordinator'")
    return UUID(payload["external_id"])


def require_status(*allowed: EnrollmentStatus):
    """Gate de status do Enrollment. Aceita um ou mais status válidos.

    Carrega o agregado de matrícula do JWT.external_id; barra (403) se o
    status atual não estiver na lista permitida. Retorna o external_id do
    matriculando (UUID) para uso no endpoint.
    """
    allowed_values = {s.value for s in allowed}

    async def _check(
        external_id: UUID = Depends(get_current_external_id),
        session: AsyncSession = Depends(get_session),
    ) -> UUID:
        enrollment = await enrollment_svc.get(session, external_id)
        if enrollment is None:
            raise HTTPException(404, "Matrícula não encontrada")
        if enrollment.status not in allowed_values:
            expected = " ou ".join(s.value for s in allowed)
            raise HTTPException(
                403, f"Status '{enrollment.status}' — requer '{expected}'"
            )
        return external_id

    return Depends(_check)


def require_started():
    return require_status(EnrollmentStatus.STARTED)


def require_profile():
    return require_status(EnrollmentStatus.PROFILE)


def require_address():
    return require_status(EnrollmentStatus.ADDRESS)


def require_documents():
    return require_status(EnrollmentStatus.DOCUMENTS)


def require_education():
    return require_status(EnrollmentStatus.EDUCATION)


def require_selfie():
    return require_status(EnrollmentStatus.SELFIE)


def require_awaiting_release():
    return require_status(EnrollmentStatus.AWAITING_RELEASE)
