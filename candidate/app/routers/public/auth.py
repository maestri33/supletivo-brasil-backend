from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import Field

from app.config import settings
from app.integrations.auth import AuthClient
from app.integrations.jwt import JwtClient
from app.models import Lead, LeadStatus
from app.notify.handlers import notify_lead_captured, notify_hub_captured
from app.schemas import APIModel

router = APIRouter(
    prefix="/api/v1/public",
    tags=["public"],
)


# ============================================================================
# Schemas
# ============================================================================

class CheckRequest(APIModel):
    cpf: str | None = None
    phone: str | None = None
    external_id: UUID | None = None


class CheckResponse(APIModel):
    found: bool
    external_id: UUID | None = None
    valid: bool | None = None
    otp_wait: int | None = None


class RegisterRequest(APIModel):
    phone: str
    cpf: str
    hub_external_id: UUID | None = None


class RegisterResponse(APIModel):
    external_id: UUID
    message: str


class LoginRequest(APIModel):
    external_id: UUID
    otp: str = Field(..., min_length=4, max_length=10)


class LoginResponse(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    status: str


class RefreshRequest(APIModel):
    refresh_token: str


class RefreshResponse(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ============================================================================
# Routes
# ============================================================================

@router.post(
    "/check",
    response_model=CheckResponse,
    summary="Verifica lead e dispara OTP",
)
async def check(payload: CheckRequest):
    if not any([payload.cpf, payload.phone, payload.external_id]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="cpf, phone ou external_id obrigatorio",
        )

    async with httpx.AsyncClient(
        base_url=settings.AUTH_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        auth = AuthClient(client)
        return await auth.check(
            cpf=payload.cpf,
            phone=payload.phone,
            external_id=str(payload.external_id) if payload.external_id else None,
        )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra novo lead",
)
async def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
):
    hub_external_id = (
        str(payload.hub_external_id)
        if payload.hub_external_id
        else settings.HUB_DEFAULT
    )

    async with httpx.AsyncClient(
        base_url=settings.AUTH_BASE_URL,
        timeout=15,
    ) as client:
        auth = AuthClient(client)

        try:
            result = await auth.register(
                phone=payload.phone,
                cpf=payload.cpf,
            )
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            try:
                detail = exc.response.json()
            except Exception:
                pass
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=detail,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha ao comunicar com auth: {exc}",
            )

    external_id = result.get("external_id")
    if not external_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Auth nao retornou external_id",
        )

    lead, created = await Lead.get_or_create(
        external_id=external_id,
        defaults={
            "status": LeadStatus.CAPTURED,
            "hub_external_id": hub_external_id,
        },
    )

    if created:
        background_tasks.add_task(notify_lead_captured, external_id)
        background_tasks.add_task(
            notify_hub_captured,
            external_id,
            payload.phone,
            hub_external_id,
        )

    return RegisterResponse(
        external_id=external_id,
        message="Cadastro realizado. OTP enviado.",
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Valida OTP e gera JWT",
)
async def login(payload: LoginRequest):
    async with httpx.AsyncClient(
        base_url=settings.AUTH_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        auth = AuthClient(client)

        try:
            tokens = await auth.login(
                external_id=str(payload.external_id),
                otp=payload.otp,
            )
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            try:
                detail = exc.response.json()
            except Exception:
                pass
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=detail,
            )

    lead = await Lead.get_or_none(external_id=payload.external_id)
    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        status=lead.status if lead else "unknown",
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Renova tokens JWT",
)
async def refresh(payload: RefreshRequest):
    async with httpx.AsyncClient(
        base_url=settings.JWT_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        jwt_client = JwtClient(client)

        try:
            tokens = await jwt_client.refresh_token(payload.refresh_token)
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            try:
                detail = exc.response.json()
            except Exception:
                pass
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=detail,
            )

    return RefreshResponse(**tokens)
