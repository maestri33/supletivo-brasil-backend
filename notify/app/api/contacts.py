"""Endpoints de contactos — CRUD e verificação (SQLAlchemy 2)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.contact import ContactCheckResponse, ContactCreate, ContactEmailUpdate, ContactRead
from app.services import contact_service

router = APIRouter()


@router.get("/check", response_model=ContactCheckResponse, summary="Verificar contacto")
async def check_contact(
    phone: str | None = Query(default=None),
    email: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ContactCheckResponse:
    result = await contact_service.check_contact(session, phone=phone, email=email)
    return ContactCheckResponse(**result)


@router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED, summary="Criar")
async def create_contact(
    payload: ContactCreate,
    session: AsyncSession = Depends(get_session),
) -> ContactRead:
    contact = await contact_service.create_contact(session, payload)
    return ContactRead.model_validate(contact, from_attributes=True)


@router.get("", response_model=list[ContactRead], summary="Listar contactos")
async def list_contacts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[ContactRead]:
    contacts = await contact_service.list_contacts(session, limit=limit, offset=offset)
    return [ContactRead.model_validate(c, from_attributes=True) for c in contacts]


@router.get("/{external_id}", response_model=ContactRead, summary="Obter contacto")
async def get_contact(
    external_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ContactRead:
    contact = await contact_service.get_contact_by_external_id(session, external_id)
    return ContactRead.model_validate(contact, from_attributes=True)


@router.patch(
    "/{external_id}/email",
    response_model=ContactRead,
    summary="Atualizar email do contacto",
)
async def update_email(
    external_id: UUID,
    payload: ContactEmailUpdate,
    session: AsyncSession = Depends(get_session),
) -> ContactRead:
    contact = await contact_service.update_email(session, external_id, payload.email)
    return ContactRead.model_validate(contact, from_attributes=True)


@router.delete(
    "/{external_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deletar contacto",
)
async def delete_contact(
    external_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    await contact_service.delete_contact(session, external_id)
