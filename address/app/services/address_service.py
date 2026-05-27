"""Serviço de Address — CRUD atômico (SQLAlchemy 2) + webhook de eventos."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFound, ValidationError
from app.integrations.webhook import notify
from app.models.address import Address
from app.schemas.address import AddressCreate, AddressPatch, AddressRead


async def create_address(session: AsyncSession, data: AddressCreate) -> AddressRead:
    address = Address(
        external_id=data.external_id,
        kind=data.kind,
        zipcode=data.zipcode,
        street=data.street,
        number=data.number,
        complement=data.complement,
        neighborhood=data.neighborhood,
        city=data.city,
        state=data.state,
        country=data.country or "BR",
        lat=data.lat,
        lng=data.lng,
    )
    session.add(address)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        msg = str(getattr(exc, "orig", exc)).lower()
        if "addresses_external_id_fkey" in msg or "foreign key" in msg:
            raise ValidationError(
                f'external_id "{data.external_id}" não existe em auth.users',
            ) from exc
        raise ValidationError("Falha de integridade ao criar address") from exc

    await session.refresh(address)
    result = AddressRead.model_validate(address)
    await notify("address.created", result.model_dump(mode="json"))
    return result


async def get_address(session: AsyncSession, address_id: UUID) -> AddressRead:
    address = await session.get(Address, address_id)
    if not address:
        raise NotFound(f'Address "{address_id}" não encontrado')
    return AddressRead.model_validate(address)


async def list_addresses(
    session: AsyncSession,
    *,
    external_id: UUID | None = None,
    kind: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[AddressRead]:
    capped_limit = max(1, min(int(limit or 20), 100))
    safe_offset = max(0, int(offset or 0))

    stmt = select(Address)
    if external_id is not None:
        stmt = stmt.where(Address.external_id == external_id)
    if kind:
        stmt = stmt.where(Address.kind == kind)
    stmt = stmt.order_by(Address.created_at.desc()).limit(capped_limit).offset(safe_offset)

    result = await session.scalars(stmt)
    return [AddressRead.model_validate(a) for a in result.all()]


async def list_by_external_id(
    session: AsyncSession,
    external_id: UUID,
) -> list[AddressRead]:
    return await list_addresses(session, external_id=external_id, limit=100)


async def current_by_kind(
    session: AsyncSession,
    external_id: UUID,
    kind: str,
) -> AddressRead:
    address = await session.scalar(
        select(Address)
        .where(Address.external_id == external_id, Address.kind == kind)
        .order_by(Address.created_at.desc())
        .limit(1)
    )
    if not address:
        raise NotFound(
            f'Nenhum endereço "{kind}" encontrado para external_id "{external_id}"',
        )
    return AddressRead.model_validate(address)


async def patch_address(
    session: AsyncSession,
    address_id: UUID,
    data: AddressPatch,
) -> AddressRead:
    address = await session.get(Address, address_id)
    if not address:
        raise NotFound(f'Address "{address_id}" não encontrado')

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        return AddressRead.model_validate(address)

    for field, value in updates.items():
        setattr(address, field, value)

    await session.commit()
    await session.refresh(address)
    result = AddressRead.model_validate(address)
    await notify("address.updated", result.model_dump(mode="json"))
    return result


async def delete_address(session: AsyncSession, address_id: UUID) -> None:
    address = await session.get(Address, address_id)
    if not address:
        raise NotFound(f'Address "{address_id}" não encontrado')
    payload = AddressRead.model_validate(address).model_dump(mode="json")
    await session.delete(address)
    await session.commit()
    await notify("address.deleted", payload)
