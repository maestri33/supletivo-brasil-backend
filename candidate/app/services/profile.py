"""Etapas de perfil (captured/personal/education/birth).

Dados persistem no `profiles` (e o email no `notify`); aqui so' orquestramos as
chamadas e avancamos o status do Candidate.
"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import NotFound
from app.integrations.notify import NotifyClient
from app.integrations.profiles import ProfilesClient
from app.models import CandidateStatus
from app.services import candidate as candidate_svc

settings = get_settings()


def _is_blank(value: str | None) -> bool:
    return not value or value.strip() == ""


def _profiles_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.profiles_base_url, timeout=settings.http_timeout)


def _notify_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.notify_base_url, timeout=settings.http_timeout)


async def _context(external_id: str) -> tuple[dict, dict]:
    """Perfil (first-name) + contato (phone/email) do candidato."""
    async with _profiles_client() as p_http, _notify_client() as n_http:
        profile = await ProfilesClient(p_http).first_name(external_id)
        contact = await NotifyClient(n_http).get_contact(external_id)
    return profile, contact


# ── captured ────────────────────────────────────────────────────────────────


async def get_captured(external_id: str) -> dict:
    profile, contact = await _context(external_id)
    return {
        "name": profile.get("first_name") or profile.get("full_name"),
        "phone": contact.get("phone"),
        "email": contact.get("email"),
    }


async def save_captured(session: AsyncSession, external_id: str, name: str, email: str) -> dict:
    """Salva nome (profiles) e email (notify). Avanca para personal quando completo.

    Retorna {"errors": {...}} se o upstream recusar, senao
    {"status": ..., "incomplete": bool, "name"/"phone"/"email"}.
    """
    errors: dict[str, str] = {}

    async with _profiles_client() as client:
        try:
            await ProfilesClient(client).patch(external_id, name=name)
        except httpx.HTTPStatusError as exc:
            errors["name"] = _upstream(exc)

    async with _notify_client() as client:
        try:
            await NotifyClient(client).update_email(external_id, email)
        except httpx.HTTPStatusError as exc:
            errors["email"] = _upstream(exc)

    if errors:
        return {"errors": errors}

    profile, contact = await _context(external_id)
    current_name = profile.get("first_name") or profile.get("full_name") or ""
    current_phone = contact.get("phone") or ""
    current_email = contact.get("email") or ""

    if _is_blank(current_name) or _is_blank(current_email) or _is_blank(current_phone):
        return {
            "incomplete": True,
            "status": "incomplete",
            "name": current_name or None,
            "phone": current_phone or None,
            "email": current_email or None,
        }

    candidate = await _load(session, external_id)
    candidate_svc.advance(candidate, CandidateStatus.CAPTURED, CandidateStatus.PERSONAL)
    return {
        "incomplete": False,
        "status": candidate.status,
        "name": current_name,
        "phone": current_phone,
        "email": current_email,
    }


# ── personal / educational / birth ──────────────────────────────────────────


async def get_profile_fields(external_id: str, fields: tuple[str, ...]) -> dict:
    async with _profiles_client() as client:
        data = await ProfilesClient(client).get_one(external_id)
    return {f: data.get(f) for f in fields}


async def save_profile_step(
    session: AsyncSession,
    external_id: str,
    *,
    current: CandidateStatus,
    new: CandidateStatus,
    patch: dict,
) -> str:
    """Patch generico em profiles + avanco de status. Retorna o status final."""
    async with _profiles_client() as client:
        await ProfilesClient(client).patch(external_id, **patch)
    candidate = await _load(session, external_id)
    candidate_svc.advance(candidate, current, new)
    return candidate.status


# ── helpers ──────────────────────────────────────────────────────────────────


async def _load(session: AsyncSession, external_id: str):
    candidate = await candidate_svc.get(session, external_id)
    if not candidate:
        raise NotFound("Candidato nao encontrado")
    return candidate


def _upstream(exc: httpx.HTTPStatusError) -> str:
    try:
        return str(exc.response.json())
    except Exception:  # noqa: BLE001
        return exc.response.text
