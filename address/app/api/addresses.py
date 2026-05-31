"""Endpoints REST de Address."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.exceptions import NotFound
from app.integrations import viacep
from app.schemas.address import AddressCreate, AddressPatch, AddressRead, ViaCepResult
from app.services.address_service import (
    create_address,
    current_by_kind,
    delete_address,
    get_address,
    list_addresses,
    list_by_external_id,
    patch_address,
)
from app.validators.zipcode import validate_zipcode

router = APIRouter(prefix="/api/v1/addresses", tags=["addresses"])


@router.post("", response_model=AddressRead, status_code=201)
async def create(data: AddressCreate, session: AsyncSession = Depends(get_session)):
    return await create_address(session, data)


@router.get("", response_model=list[AddressRead])
async def list_all(
    session: AsyncSession = Depends(get_session),
    external_id: UUID | None = Query(None, description="Filtra por dono"),
    kind: str | None = Query(None, description="home|billing|shipping"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return await list_addresses(
        session,
        external_id=external_id,
        kind=kind,
        limit=limit,
        offset=offset,
    )


@router.get("/by-external-id/{external_id}", response_model=list[AddressRead])
async def by_external_id(external_id: UUID, session: AsyncSession = Depends(get_session)):
    return await list_by_external_id(session, external_id)


@router.get(
    "/by-external-id/{external_id}/{kind}/current",
    response_model=AddressRead,
)
async def current(
    external_id: UUID,
    kind: str,
    session: AsyncSession = Depends(get_session),
):
    return await current_by_kind(session, external_id, kind)


@router.get("/cep/{zipcode}", response_model=ViaCepResult)
async def viacep_lookup(zipcode: str):
    """Lookup ViaCEP — feature do LOCAL, preenche o gap da produção."""
    clean = validate_zipcode(zipcode)
    data = await viacep.lookup(clean)
    if not data:
        raise NotFound(f'CEP "{clean}" não encontrado na ViaCEP')
    return data


@router.get("/{address_id}", response_model=AddressRead)
async def get_one(address_id: UUID, session: AsyncSession = Depends(get_session)):
    return await get_address(session, address_id)


@router.patch("/{address_id}", response_model=AddressRead)
async def patch(
    address_id: UUID,
    data: AddressPatch,
    session: AsyncSession = Depends(get_session),
):
    return await patch_address(session, address_id, data)


@router.delete("/{address_id}", status_code=204)
async def delete_one(address_id: UUID, session: AsyncSession = Depends(get_session)):
    await delete_address(session, address_id)
