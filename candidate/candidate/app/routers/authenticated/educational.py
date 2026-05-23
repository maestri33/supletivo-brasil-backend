from fastapi import APIRouter, HTTPException, status
from pydantic import Field

from app.dependencies import require_education
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

class EducationalGetResponse(APIModel):
    message: str = "Preencha seus dados educacionais"
    education_level: str | None = None
    institution: str | None = None
    course: str | None = None
    completion_year: int | None = None


class EducationalPostRequest(APIModel):
    education_level: str = Field(..., min_length=2, max_length=100)
    institution: str = Field(..., min_length=2, max_length=200)
    course: str | None = Field(None, max_length=200)
    completion_year: int | None = Field(None, ge=1950, le=2100)


class EducationalPostResponse(APIModel):
    status: str
    message: str = "Dados educacionais salvos, preencha dados de nascimento"


# ============================================================================
# Routes
# ============================================================================

@router.get(
    "/educational",
    response_model=EducationalGetResponse,
    summary="Busca dados educacionais do lead",
)
async def get_educational(
    external_id: str = require_education(),
):
    async with httpx.AsyncClient(
        base_url=settings.PROFILES_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        profiles = ProfilesClient(client)
        data = await profiles.get_one(external_id)

    return EducationalGetResponse(
        education_level=data.get("education_level"),
        institution=data.get("institution"),
        course=data.get("course"),
        completion_year=data.get("completion_year"),
    )


@router.post(
    "/educational",
    response_model=EducationalPostResponse,
    summary="Salva dados educacionais, avanca para birth",
)
async def post_educational(
    payload: EducationalPostRequest,
    external_id: str = require_education(),
):
    async with httpx.AsyncClient(
        base_url=settings.PROFILES_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        profiles = ProfilesClient(client)

        try:
            await profiles.patch(
                external_id,
                education_level=payload.education_level,
                institution=payload.institution,
                course=payload.course,
                completion_year=payload.completion_year,
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

    if lead.status == LeadStatus.EDUCATION:
        lead.status = LeadStatus.BIRTH
        await lead.save(update_fields=["status", "updated_at"])

    return EducationalPostResponse(status=lead.status)
