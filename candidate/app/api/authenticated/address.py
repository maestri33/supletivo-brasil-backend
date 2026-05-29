"""Etapa address — endereco (CEP primeiro); avanca para documents."""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.db import get_session
from app.dependencies import require_address
from app.schemas.address import (
    AddressGetResponse,
    AddressPostRequest,
    AddressPostResponse,
    CepCheckResponse,
)
from app.services import address as address_svc
from app.services import notifications

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


@router.get("/address", response_model=AddressGetResponse, summary="Endereco do candidato")
async def get_address(external_id=require_address()):
    with upstream_errors():
        data = await address_svc.get_address(str(external_id))
    return AddressGetResponse(**data) if data else AddressGetResponse()


@router.get(
    "/address/cep/{cep}",
    response_model=CepCheckResponse,
    summary="Consulta CEP via address-service",
)
async def check_cep(cep: str, external_id=require_address()):
    with upstream_errors():
        result = await address_svc.check_cep(cep)
    return CepCheckResponse(
        cep=result["cep"],
        formatted=result["formatted"],
        valid=result["valid"],
        street=result.get("street"),
        neighborhood=result.get("neighborhood"),
        city=result.get("city"),
        state=result.get("state"),
    )


@router.post("/address", response_model=AddressPostResponse, summary="Salva endereco")
async def post_address(
    payload: AddressPostRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    external_id=require_address(),
):
    with upstream_errors():
        new_status = await address_svc.save_address(session, str(external_id), payload)
    await session.commit()
    background_tasks.add_task(notifications.notify_status_advanced, str(external_id), new_status)
    return AddressPostResponse(status=new_status)
