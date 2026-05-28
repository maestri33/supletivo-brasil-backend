"""Dependencies — sessão DB, validação JWT/JWKS, gates por status."""

import time
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Lead, LeadStatus

_jwks_cache: dict | None = None
_jwks_cached_at: float = 0.0


async def get_jwks() -> dict:
    """Cache JWKS por 5 min — evita N requests por validação."""
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
) -> UUID:
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

    if "lead" not in payload.get("roles", []):
        raise HTTPException(403, "Requires 'lead' role")

    return UUID(payload["external_id"])


def _require_status(*required: LeadStatus):
    """Gate por status do Lead. Aceita um OU mais status validos.

    Multi-status e' util pra endpoints que devem responder durante e apos
    uma transicao (ex.: GET /checkout serve tanto durante CHECKOUT quanto
    COMPLETED, para suportar polling de status sem perder a transicao).
    """
    allowed = set(required)

    async def check_status(
        external_id: UUID = Depends(get_current_external_id),
        session: AsyncSession = Depends(get_session),
    ) -> UUID:
        lead = await session.scalar(select(Lead).where(Lead.external_id == external_id))
        if not lead:
            raise HTTPException(404, "Lead not found")
        if lead.status not in allowed:
            expected = " or ".join(s.value for s in required)
            raise HTTPException(
                403,
                f"Status '{lead.status.value}' — requires '{expected}'",
            )
        return external_id

    return Depends(check_status)


def require_captured():
    return _require_status(LeadStatus.CAPTURED)


def require_waiting():
    # Aceita WAITING ou FAILED — front continua pollando /waiting depois que
    # o BG task falhou; o handler retorna error_code junto com o status.
    return _require_status(LeadStatus.WAITING, LeadStatus.FAILED)


def require_checkout():
    # Aceita CHECKOUT ou COMPLETED — frontend polla GET /checkout esperando
    # is_paid=true; se o webhook chegou entre dois polls, o lead ja' esta
    # em COMPLETED e queremos retornar is_paid=true (nao 403).
    return _require_status(LeadStatus.CHECKOUT, LeadStatus.COMPLETED)


def require_completed():
    return _require_status(LeadStatus.COMPLETED)
