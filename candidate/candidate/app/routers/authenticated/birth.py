from datetime import date

from fastapi import APIRouter, HTTPException, status
from pydantic import Field

from app.dependencies import require_birth
from app.integrations.profiles import ProfilesClient
from app.models import Lead, LeadStatus
from app.schemas import APIModel
from app.config import settings

import httpx

router = APIRouter(
    prefix="/api/v1/authenticated",
    tags=["authenticated"],
)


# ============================================================================
# Schemas
# ============================================================================

class BirthGetResponse(APIModel):
    message: str = "Preencha seus dados de nascimento"
    date_of_birth: date | None = None
    birthplace: str | None = None
    nationality: str | None = None


class BirthPostRequest(APIModel):
    date_of_birth: date = Field(..., description="Data de nascimento")
    birthplace: str = Field(..., min_length=2, max_length=200, description="Cidade/Estado onde nasceu")
    nationality: str = Field(..., min_length=2, max_length=100, description="Nacionalidade")


class BirthPostResponse(APIModel):
    status: str
    message: str = "Dados de nascimento salvos, cadastro concluido"


# ============================================================================
# Routes
# ============================================================================

@router.get(
    "/birth",
    response_model=BirthGetResponse,
    summary="Busca dados de nascimento do lead",
)
async def get_birth(
    external_id: str = require_birth(),
):
    async with httpx.AsyncClient(
        base_url=settings.PROFILES_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        profiles = ProfilesClient(client)
        data = await profiles.get_one(external_id)

    return BirthGetResponse(
        date_of_birth=data.get("date_of_birth"),
        birthplace=data.get("birthplace"),
        nationality=data.get("nationality"),
    )


@router.post(
    "/birth",
    response_model=BirthPostResponse,
    summary="Salva dados de nascimento, avanca para waiting",
)
async def post_birth(
    payload: BirthPostRequest,
    external_id: str = require_birth(),
):
    async with httpx.AsyncClient(
        base_url=settings.PROFILES_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        profiles = ProfilesClient(client)

        try:
            await profiles.patch(
                external_id,
                date_of_birth=payload.date_of_birth.isoformat(),
                birthplace=payload.birthplace,
                nationality=payload.nationality,
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

    if lead.status == LeadStatus.BIRTH:
        lead.status = LeadStatus.WAITING
        await lead.save(update_fields=["status", "updated_at"])

    return BirthPostResponse(status=lead.status)
