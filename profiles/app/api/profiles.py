"""Endpoints REST de Profile (SQLAlchemy 2)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.profile import (
    CPFCheckResponse,
    FirstNameResponse,
    ProfileCreate,
    ProfileListItem,
    ProfilePatch,
    ProfileRead,
)
from app.services.profile_service import (
    create_profile,
    delete_profile,
    get_first_name,
    get_profile,
    get_profile_by_cpf,
    list_profiles,
    patch_profile,
)

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


@router.post("", response_model=ProfileRead, status_code=201)
async def create(data: ProfileCreate, session: AsyncSession = Depends(get_session)):
    return await create_profile(session, data)


@router.get("/cpf/{cpf}", response_model=CPFCheckResponse)
async def check_cpf(cpf: str, session: AsyncSession = Depends(get_session)):
    return await get_profile_by_cpf(session, cpf)


@router.get("/first-name/{external_id}", response_model=FirstNameResponse)
async def get_first_name_endpoint(
    external_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_first_name(session, external_id)


@router.get("", response_model=list[ProfileListItem])
async def list_all(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(20, ge=1, le=100, description="Máx. de itens (1..100)"),
    offset: int = Query(0, ge=0, description="Quantos itens pular"),
    q: str | None = Query(None, max_length=100, description="Busca prefix em name"),
    cpf: str | None = Query(None, max_length=14, description="Filtro prefix por CPF"),
):
    return await list_profiles(session, limit=limit, offset=offset, q=q, cpf=cpf)


@router.get("/{external_id}", response_model=ProfileRead)
async def get_one(external_id: UUID, session: AsyncSession = Depends(get_session)):
    return await get_profile(session, external_id)


@router.patch("/{external_id}", response_model=ProfileRead)
async def patch(
    external_id: UUID,
    data: ProfilePatch,
    session: AsyncSession = Depends(get_session),
):
    return await patch_profile(session, external_id, data)


@router.delete("/{external_id}", status_code=204)
async def delete_one(external_id: UUID, session: AsyncSession = Depends(get_session)):
    await delete_profile(session, external_id)
