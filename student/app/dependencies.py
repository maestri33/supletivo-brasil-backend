"""Dependencies — validacao JWT/JWKS, gate por role e por status do Student."""

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
from app.models import Student, StudentStatus

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


def require_student_with_status(*allowed: StudentStatus):
    """Aluno autenticado cujo status esta na lista `allowed`. Carrega o Student
    a partir do external_id do JWT — uma so' consulta na DB, reaproveitada pela rota.
    """
    allowed_values = {s.value for s in allowed}

    async def _check(
        payload: dict = Depends(get_token_payload),
        session: AsyncSession = Depends(get_session),
    ) -> Student:
        if "student" not in payload.get("roles", []):
            raise HTTPException(403, "Requires 'student' role")
        external_id = UUID(payload["external_id"])
        student = await session.scalar(select(Student).where(Student.external_id == external_id))
        if student is None:
            raise HTTPException(404, "Student not found")
        if student.status.value not in allowed_values:
            expected = " ou ".join(sorted(allowed_values))
            raise HTTPException(403, f"Status '{student.status.value}' — requer '{expected}'")
        return student

    return Depends(_check)
