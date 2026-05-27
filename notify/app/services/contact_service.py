"""Serviço de contactos — CRUD e verificação (SQLAlchemy 2)."""

import re
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import Conflict, DomainError, NotFound
from app.utils.logging import get_logger
from app.utils.pii import mask_phone as _mask_phone
from app.models.contact import Contact
from app.models.log import Log
from app.models.message import Message
from app.schemas.contact import ContactCreate
from app.utils.email_validator import validate_email as validate_email_full
from app.utils.logging import get_logger
from app.utils.phone import normalize_and_validate

log = get_logger(__name__)

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _validate_email_format(email: str) -> bool:
    return bool(_EMAIL_RE.match(email))


async def create_contact(session: AsyncSession, payload: ContactCreate) -> Contact:
    """Cria um contacto com validação de telefone e unicidade."""
    if not payload.phone and not payload.email:
        raise DomainError("Pelo menos telefone ou email deve ser informado")

    existing = await session.scalar(
        select(Contact).where(Contact.external_id == payload.external_id)
    )
    if existing:
        raise Conflict(f"Contacto {payload.external_id} ja existe")

    normalized_phone: str | None = None
    if payload.phone:
        dup = await session.scalar(select(Contact).where(Contact.phone == payload.phone))
        if dup:
            raise Conflict(f"Telefone {payload.phone} ja pertence ao contacto {dup.external_id}")

        try:
            normalized_phone = await normalize_and_validate(payload.phone)
        except ValueError as exc:
            raise DomainError(str(exc)) from exc

        if normalized_phone != payload.phone:
            dup = await session.scalar(select(Contact).where(Contact.phone == normalized_phone))
            if dup:
                raise Conflict(
                    f"Telefone {normalized_phone} ja pertence ao contacto {dup.external_id}"
                )

    if payload.email:
        dup = await session.scalar(select(Contact).where(Contact.email == payload.email))
        if dup:
            raise Conflict(f"Email {payload.email} ja pertence ao contacto {dup.external_id}")
        validation = await validate_email_full(payload.email)
        if not validation.valid_format:
            raise DomainError(f"Email com formato invalido: {payload.email}")
        if not validation.has_mx:
            raise DomainError(
                f"Dominio '{validation.domain}' nao possui servidor de email (MX). "
                f"Verifique se o email esta correto."
            )
        if not validation.is_valid:
            raise DomainError(f"Email nao validado: {payload.email}")

    contact = Contact(
        external_id=payload.external_id,
        phone=normalized_phone or payload.phone,
        email=payload.email,
    )
    session.add(contact)
    session.add(
        Log(
            external_id=contact.external_id,
            action="contact.created",
            details={
                "external_id": str(payload.external_id),
                "phone_original": payload.phone,
                "phone_normalized": normalized_phone,
                "has_email": bool(payload.email),
            },
        )
    )
    await session.commit()
    await session.refresh(contact)
    log.info("contact.created", external_id=str(payload.external_id), phone=_mask_phone(normalized_phone))
    return contact


async def get_contact_by_external_id(session: AsyncSession, external_id: UUID) -> Contact:
    contact = await session.scalar(select(Contact).where(Contact.external_id == external_id))
    if contact is None:
        raise NotFound(f"Contacto {external_id} nao encontrado")
    return contact


async def update_email(session: AsyncSession, external_id: UUID, email: str) -> Contact:
    """Adiciona ou atualiza o email de um contacto."""
    contact = await get_contact_by_external_id(session, external_id)

    validation = await validate_email_full(email)
    if not validation.valid_format:
        raise DomainError(f"Email com formato invalido: {email}")
    if not validation.has_mx:
        raise DomainError(
            f"Dominio '{validation.domain}' nao possui servidor de email (MX). "
            f"Verifique se o email esta correto."
        )

    dup = await session.scalar(select(Contact).where(Contact.email == email))
    if dup and dup.id != contact.id:
        raise Conflict(f"Email {email} ja pertence ao contacto {dup.external_id}")

    contact.email = email
    session.add(
        Log(
            external_id=external_id,
            action="contact.email_updated",
            details={"external_id": str(external_id), "email": email},
        )
    )
    await session.commit()
    await session.refresh(contact)
    log.info("contact.email_updated", external_id=str(external_id))
    return contact


async def delete_contact(session: AsyncSession, external_id: UUID) -> None:
    """Destroi um contacto e todas as suas mensagens e logs."""
    contact = await get_contact_by_external_id(session, external_id)

    messages = await session.scalars(select(Message).where(Message.contact_id == contact.id))
    message_ids = [m.id for m in messages.all()]
    if message_ids:
        await session.execute(delete(Log).where(Log.message_id.in_(message_ids)))
    await session.execute(delete(Message).where(Message.contact_id == contact.id))
    await session.delete(contact)
    await session.commit()
    log.info("contact.deleted", external_id=str(external_id), messages=len(message_ids))


async def list_contacts(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[Contact]:
    result = await session.scalars(select(Contact).offset(offset).limit(limit))
    return list(result.all())


async def check_contact(
    session: AsyncSession,
    phone: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    """Verifica se um contacto existe — apenas consulta, nunca cria."""
    if not phone and not email:
        raise DomainError("Pelo menos telefone ou email deve ser informado")

    contact = None
    normalized: str | None = None
    if phone:
        contact = await session.scalar(select(Contact).where(Contact.phone == phone))
        if not contact:
            try:
                normalized = await normalize_and_validate(phone)
                contact = await session.scalar(select(Contact).where(Contact.phone == normalized))
            except ValueError:
                pass

    if not contact and email:
        contact = await session.scalar(select(Contact).where(Contact.email == email))

    if contact:
        log.info("contact.check_found", external_id=str(contact.external_id))
        return {
            "found": True,
            "external_id": str(contact.external_id),
            "phone": contact.phone,
            "email": contact.email,
        }

    phone_valid: bool | None = None
    email_valid: bool | None = None

    if email:
        email_valid = _validate_email_format(email)

    if phone:
        phone_valid = bool(normalized)

    log.info(
        "contact.check_not_found",
        phone=normalized or phone,
        phone_valid=phone_valid,
        email_valid=email_valid,
    )
    return {
        "found": False,
        "phone_valid": phone_valid,
        "email_valid": email_valid,
    }
