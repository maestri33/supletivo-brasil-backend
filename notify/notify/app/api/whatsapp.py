"""Endpoints de WhatsApp — perfil (SQLAlchemy 2)."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.whatsapp import WhatsAppProfile, WhatsAppProfileList
from app.services import whatsapp_profile_service

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.get(
    "/profile/{external_id}",
    response_model=WhatsAppProfile,
    summary="Perfil WhatsApp do contacto",
)
async def get_profile(
    external_id: UUID, session: AsyncSession = Depends(get_session),
) -> WhatsAppProfile:
    return await whatsapp_profile_service.fetch_contact_profile(session, external_id)


@router.get(
    "/profiles",
    response_model=WhatsAppProfileList,
    summary="Todos os perfis WhatsApp",
)
async def list_profiles(
    session: AsyncSession = Depends(get_session),
) -> WhatsAppProfileList:
    items = await whatsapp_profile_service.fetch_all_profiles(session)
    return WhatsAppProfileList(count=len(items), items=items)
