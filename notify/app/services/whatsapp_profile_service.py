"""Serviço de perfis WhatsApp — fetch individual ou em lote (SQLAlchemy 2)."""

from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.whatsapp import WhatsAppClient
from app.models.contact import Contact
from app.schemas.whatsapp import WhatsAppProfile
from app.utils.logging import get_logger

log = get_logger(__name__)

ALL_FIELDS = {
    "name", "picture", "status", "description", "website",
    "email", "address", "category", "business_hours",
}


async def _fetch_profile(phone: str, external_id: UUID) -> WhatsAppProfile:
    profile = WhatsAppProfile(external_id=external_id, phone=phone)

    async with httpx.AsyncClient() as http:
        client = WhatsAppClient(http)

        try:
            data = await client.fetch_profile(phone)
            profile.name = data.get("name", "") or ""
            profile.is_business = data.get("isBusiness", False)
            pic = data.get("picture", "")
            profile.picture = pic or ""
            profile.has_picture = bool(pic)
            st = data.get("status", {}) or {}
            profile.status = st.get("status", "") or ""
            profile.description = data.get("description", "") or ""
            site = data.get("website", "")
            profile.website = (
                (site[0] if isinstance(site, list) and site else site) if site else ""
            )

            if profile.is_business:
                try:
                    biz = await client.fetch_business_profile(phone)
                    profile.address = biz.get("address", "") or ""
                    profile.email = biz.get("email", "") or ""
                    profile.category = biz.get("category", "") or ""
                    wh = biz.get("website", []) or []
                    if wh and not profile.website:
                        profile.website = wh[0] if isinstance(wh, list) else str(wh)
                    hrs = biz.get("business_hours", {}) or {}
                    profile.business_hours = hrs.get("timezone", "") or ""
                    if profile.description:
                        profile.description = biz.get("description") or profile.description
                except Exception as exc:
                    log.warning("business_profile_failed", phone=phone, error=str(exc))

            log.info(
                "whatsapp.profile_fetched",
                external_id=str(external_id), is_business=profile.is_business,
            )

        except Exception as exc:
            log.error("profile_fetch_failed", phone=phone, error=str(exc))
            profile.error = str(exc)

    return profile


async def fetch_contact_profile(
    session: AsyncSession, external_id: UUID,
) -> WhatsAppProfile:
    contact = await session.scalar(
        select(Contact).where(Contact.external_id == external_id)
    )
    if not contact:
        from app.exceptions import NotFound
        raise NotFound(f"Contacto {external_id} nao encontrado")
    if not contact.phone:
        from app.exceptions import DomainError
        raise DomainError(f"Contacto {external_id} nao possui telefone")
    return await _fetch_profile(contact.phone, external_id)


async def fetch_all_profiles(session: AsyncSession) -> list[WhatsAppProfile]:
    """Busca perfil WhatsApp de todos os contactos que tem telefone."""
    result = await session.scalars(select(Contact).where(Contact.phone.is_not(None)))
    contacts = list(result.all())
    results: list[WhatsAppProfile] = []
    for c in contacts:
        profile = await _fetch_profile(c.phone, c.external_id)
        results.append(profile)
    log.info("whatsapp.profiles_batch", count=len(results))
    return results
