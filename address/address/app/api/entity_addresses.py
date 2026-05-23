"""Endpoints REST de EntityAddress (vínculo polimórfico) — feature do LOCAL."""

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.entity_address import EntityAddressRead
from app.services import entity_address_service

router = APIRouter(prefix="/api/v1/entities", tags=["entities"])


@router.get("/{entity_type}/{external_id}", response_model=EntityAddressRead)
async def get_entity_address(
    entity_type: str, external_id: str, session: AsyncSession = Depends(get_session),
):
    return await entity_address_service.get_or_create(session, entity_type, external_id)


@router.post("/{entity_type}/{external_id}/cep", response_model=EntityAddressRead)
async def update_cep(
    entity_type: str,
    external_id: str,
    cep: str = Query(..., description="CEP a consultar na ViaCEP"),
    session: AsyncSession = Depends(get_session),
):
    return await entity_address_service.update_address_by_cep(
        session, entity_type, external_id, cep,
    )


@router.post("/{entity_type}/{external_id}/proof", response_model=EntityAddressRead)
async def upload_proof(
    entity_type: str,
    external_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    return await entity_address_service.upload_proof(session, entity_type, external_id, file)


@router.post("/{entity_type}/{external_id}/unlink", response_model=EntityAddressRead)
async def unlink_address(
    entity_type: str, external_id: str, session: AsyncSession = Depends(get_session),
):
    return await entity_address_service.unlink_and_create_new(session, entity_type, external_id)
