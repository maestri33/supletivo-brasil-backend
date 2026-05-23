from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import Field

from app.config import settings
from app.dependencies import require_address
from app.integrations.address import AddressClient
from app.models import Lead, LeadStatus
from app.schemas import APIModel

import httpx

router = APIRouter(
    prefix="/api/v1/authenticated",
    tags=["authenticated"],
)


# ============================================================================
# Schemas
# ============================================================================

class AddressGetResponse(APIModel):
    message: str = "Preencha seu endereco"
    cep: str | None = None
    street: str | None = None
    number: str | None = None
    complement: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None
    has_proof: bool = False
    proof_file: str | None = None


class CepCheckResponse(APIModel):
    cep: str
    formatted: str
    valid: bool
    street: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None


class AddressPostRequest(APIModel):
    cep: str = Field(..., min_length=8, max_length=9, description="CEP com ou sem mascara")
    street: str = Field(..., min_length=2, max_length=255)
    number: str = Field(..., min_length=1, max_length=20)
    complement: str | None = Field(None, max_length=255)
    neighborhood: str = Field(..., min_length=2, max_length=100)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=2)


class AddressPostResponse(APIModel):
    status: str
    message: str = "Endereco salvo, cadastro concluido"


# ============================================================================
# Routes
# ============================================================================

@router.get(
    "/address",
    response_model=AddressGetResponse,
    summary="Busca endereco do lead",
)
async def get_address(
    external_id: str = require_address(),
):
    async with httpx.AsyncClient(
        base_url=settings.ADDRESSES_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        address_client = AddressClient(client)

        try:
            entity = await address_client.get_entity_address(
                "lead", external_id
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return AddressGetResponse()
            raise

    addr = entity.get("address") or {}

    return AddressGetResponse(
        cep=addr.get("cep"),
        street=addr.get("street"),
        number=addr.get("number"),
        complement=addr.get("complement"),
        neighborhood=addr.get("neighborhood"),
        city=addr.get("city"),
        state=addr.get("state"),
        has_proof=bool(entity.get("proof_file")),
        proof_file=entity.get("proof_file"),
    )


@router.get(
    "/address/cep/{cep}",
    response_model=CepCheckResponse,
    summary="Consulta CEP via address-service",
)
async def check_cep(
    cep: str,
    external_id: str = require_address(),
):
    async with httpx.AsyncClient(
        base_url=settings.ADDRESSES_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        address_client = AddressClient(client)
        result = await address_client.check_cep(cep)

    return CepCheckResponse(
        cep=result["cep"],
        formatted=result["formatted"],
        valid=result["valid"],
    )


@router.post(
    "/address",
    response_model=AddressPostResponse,
    summary="Salva endereco e avanca para waiting",
)
async def post_address(
    payload: AddressPostRequest,
    external_id: str = require_address(),
):
    async with httpx.AsyncClient(
        base_url=settings.ADDRESSES_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        address_client = AddressClient(client)

        try:
            await address_client.create_address(
                street=payload.street,
                number=payload.number,
                complement=payload.complement,
                neighborhood=payload.neighborhood,
                city=payload.city,
                state=payload.state,
                cep=payload.cep,
            )

            await address_client.update_entity_cep(
                "lead", external_id, payload.cep
            )

        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json()
            except Exception:
                detail = exc.response.text
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=detail,
            )

    lead = await Lead.get_or_none(external_id=external_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead nao encontrado",
        )

    if lead.status == LeadStatus.ADDRESS:
        lead.status = LeadStatus.WAITING
        await lead.save(update_fields=["status", "updated_at"])

    return AddressPostResponse(status=lead.status)
