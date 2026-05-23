import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import EmailStr, Field

from app.config import settings
from app.dependencies import require_captured
from app.integrations.notify import NotifyClient
from app.integrations.profiles import ProfilesClient
from app.models import Lead, LeadStatus
from app.schemas import APIModel

router = APIRouter(
    prefix="/api/v1/authenticated",
    tags=["authenticated"],
)


# ============================================================================
# Schemas
# ============================================================================

class CapturedGetResponse(APIModel):
    message: str = "Insira seus dados para prosseguir"
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class CapturedPostRequest(APIModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr


class CapturedPostResponse(APIModel):
    status: str
    message: str = "Dados salvos, preencha dados pessoais"

    name: str | None = None
    phone: str | None = None
    email: str | None = None


# ============================================================================
# Helpers
# ============================================================================

def is_blank(value: str | None) -> bool:
    return not value or value.strip() == ""


async def fetch_lead_context(external_id: str):
    async with (
        httpx.AsyncClient(
            base_url=settings.PROFILES_BASE_URL,
            timeout=settings.HTTP_TIMEOUT,
        ) as profiles_http,
        httpx.AsyncClient(
            base_url=settings.NOTIFY_BASE_URL,
            timeout=settings.HTTP_TIMEOUT,
        ) as notify_http,
    ):
        profiles = ProfilesClient(profiles_http)
        notify = NotifyClient(notify_http)

        profile_data = await profiles.first_name(external_id)
        contact_data = await notify.get_contact(external_id)

    return profile_data, contact_data


# ============================================================================
# Routes
# ============================================================================

@router.get(
    "/captured",
    response_model=CapturedGetResponse,
    summary="Busca dados do lead capturado",
)
async def get_captured(
    external_id: str = require_captured(),
):
    profile_data, contact_data = await fetch_lead_context(external_id)

    return CapturedGetResponse(
        name=profile_data.get("first_name") or profile_data.get("full_name"),
        phone=contact_data.get("phone"),
        email=contact_data.get("email"),
    )


@router.post(
    "/captured",
    response_model=CapturedPostResponse,
    summary="Salva nome e email, avanca para personal",
)
async def post_captured(
    payload: CapturedPostRequest,
    background_tasks: BackgroundTasks,
    external_id: str = require_captured(),
):
    errors: dict[str, str] = {}

    async with httpx.AsyncClient(
        base_url=settings.PROFILES_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        profiles = ProfilesClient(client)
        try:
            await profiles.patch(external_id, name=payload.name)
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json()
            except Exception:
                detail = exc.response.text
            errors["name"] = str(detail)

    async with httpx.AsyncClient(
        base_url=settings.NOTIFY_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        notify = NotifyClient(client)
        try:
            await notify.update_email(external_id, payload.email)
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json()
            except Exception:
                detail = exc.response.text
            errors["email"] = str(detail)

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors,
        )

    profile_data, contact_data = await fetch_lead_context(external_id)

    current_name = profile_data.get("first_name") or profile_data.get("full_name") or ""
    current_phone = contact_data.get("phone") or ""
    current_email = contact_data.get("email") or ""

    if is_blank(current_name) or is_blank(current_email) or is_blank(current_phone):
        return CapturedPostResponse(
            status="incomplete",
            message="Preencha todos os campos para prosseguir",
            name=current_name or None,
            phone=current_phone or None,
            email=current_email or None,
        )

    lead = await Lead.get_or_none(external_id=external_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead nao encontrado",
        )

    if lead.status == LeadStatus.CAPTURED:
        lead.status = LeadStatus.PERSONAL
        await lead.save(update_fields=["status", "updated_at"])

    return CapturedPostResponse(
        status=lead.status,
        name=current_name,
        phone=current_phone,
        email=current_email,
    )
