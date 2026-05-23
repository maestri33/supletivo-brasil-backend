from fastapi import APIRouter, HTTPException, status
from pydantic import Field

from app.dependencies import require_personal
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

class PersonalGetResponse(APIModel):
    message: str = "Preencha seus dados pessoais"
    gender: str | None = None
    mother_name: str | None = None
    father_name: str | None = None
    marital_status: str | None = None


class PersonalPostRequest(APIModel):
    gender: str = Field(..., min_length=1, max_length=50)
    mother_name: str = Field(..., min_length=2, max_length=120)
    father_name: str = Field(..., min_length=2, max_length=120)
    marital_status: str = Field(..., min_length=2, max_length=50)


class PersonalPostResponse(APIModel):
    status: str
    message: str = "Dados pessoais salvos, preencha dados educacionais"


# ============================================================================
# Routes
# ============================================================================

@router.get(
    "/personal",
    response_model=PersonalGetResponse,
    summary="Busca dados pessoais do lead",
)
async def get_personal(
    external_id: str = require_personal(),
):
    async with httpx.AsyncClient(
        base_url=settings.PROFILES_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        profiles = ProfilesClient(client)
        data = await profiles.get_one(external_id)

    return PersonalGetResponse(
        gender=data.get("gender"),
        mother_name=data.get("mother_name"),
        father_name=data.get("father_name"),
        marital_status=data.get("marital_status"),
    )


@router.post(
    "/personal",
    response_model=PersonalPostResponse,
    summary="Salva dados pessoais, avanca para education",
)
async def post_personal(
    payload: PersonalPostRequest,
    external_id: str = require_personal(),
):
    async with httpx.AsyncClient(
        base_url=settings.PROFILES_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        profiles = ProfilesClient(client)

        try:
            await profiles.patch(
                external_id,
                gender=payload.gender,
                mother_name=payload.mother_name,
                father_name=payload.father_name,
                marital_status=payload.marital_status,
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

    if lead.status == LeadStatus.PERSONAL:
        lead.status = LeadStatus.EDUCATION
        await lead.save(update_fields=["status", "updated_at"])

    return PersonalPostResponse(status=lead.status)
