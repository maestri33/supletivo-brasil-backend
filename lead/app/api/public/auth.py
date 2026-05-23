"""Endpoints públicos de autenticação — check, register, login, refresh."""

from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.integrations.auth import AuthClient
from app.integrations.jwt import JwtClient
from app.models import Lead, LeadStatus
from app.notify.handlers import notify_lead_captured, notify_promoter_captured
from app.schemas import APIModel

router = APIRouter(prefix="/api/v1/public", tags=["public"])


class CheckRequest(APIModel):
    cpf: str | None = None
    phone: str | None = None
    external_id: UUID | None = None


class CheckResponse(APIModel):
    found: bool
    external_id: UUID | None = None
    valid: bool | None = None
    otp_wait: int | None = None


class LoginRequest(APIModel):
    external_id: UUID
    otp: str = Field(..., min_length=4, max_length=10)


class LoginResponse(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    status: str


class RegisterRequest(APIModel):
    phone: str
    cpf: str
    # `ref` = UUID do promoter que indicou (URL pattern padrao: ?ref=...,
    # como Stripe/Twitter/YouTube/GitHub). Internamente continua sendo o
    # external_id do service Promoter — a coluna do DB (leads.promoter_external_id)
    # e o service mantem o nome `promoter`. Apenas a interface publica usa `ref`.
    ref: UUID | None = None


class RegisterResponse(APIModel):
    external_id: UUID
    message: str


class RefreshRequest(APIModel):
    refresh_token: str


class RefreshResponse(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/check", response_model=CheckResponse, summary="Verifica lead e dispara OTP")
async def check(payload: CheckRequest):
    if not any([payload.cpf, payload.phone, payload.external_id]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="cpf, phone ou external_id obrigatorio",
        )

    # Erros 4xx do auth (ex: PHONE_INVALID quando phone tem != 10-11 digitos)
    # vinham como httpx.HTTPStatusError nao-capturada -> FastAPI default
    # handler -> HTTP 500. Espelho do tratamento do /register abaixo: propaga
    # status + detail originais; falha de transporte vira 502 BAD_GATEWAY.
    async with httpx.AsyncClient(
        base_url=settings.AUTH_BASE_URL, timeout=settings.HTTP_TIMEOUT
    ) as client:
        try:
            return await AuthClient(client).check(
                cpf=payload.cpf,
                phone=payload.phone,
                external_id=str(payload.external_id) if payload.external_id else None,
            )
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            try:
                detail = exc.response.json()
            except Exception:
                pass
            raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha ao comunicar com auth: {exc}",
            ) from exc


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra novo lead",
)
async def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    # `ref` na interface publica == `promoter_external_id` internamente.
    # Default vem do settings.PROMOTER_DEFAULT quando nao informado.
    promoter_external_id = payload.ref or UUID(settings.PROMOTER_DEFAULT)

    async with httpx.AsyncClient(
        base_url=settings.AUTH_BASE_URL, timeout=settings.HTTP_TIMEOUT + 5
    ) as client:
        try:
            result = await AuthClient(client).register(phone=payload.phone, cpf=payload.cpf)
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            try:
                detail = exc.response.json()
            except Exception:
                pass
            raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha ao comunicar com auth: {exc}",
            ) from exc

    external_id_str = result.get("external_id")
    if not external_id_str:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Auth nao retornou external_id",
        )
    external_id = UUID(external_id_str)

    lead = await session.scalar(select(Lead).where(Lead.external_id == external_id))
    created = lead is None
    if created:
        lead = Lead(
            external_id=external_id,
            status=LeadStatus.CAPTURED,
            promoter_external_id=promoter_external_id,
        )
        session.add(lead)
        await session.commit()

        background_tasks.add_task(notify_lead_captured, external_id_str)
        background_tasks.add_task(
            notify_promoter_captured,
            external_id_str,
            payload.phone,
            str(promoter_external_id),
        )

    return RegisterResponse(external_id=external_id, message="Cadastro realizado. OTP enviado.")


@router.post("/login", response_model=LoginResponse, summary="Valida OTP e gera JWT")
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)):
    async with httpx.AsyncClient(
        base_url=settings.AUTH_BASE_URL, timeout=settings.HTTP_TIMEOUT
    ) as client:
        try:
            tokens = await AuthClient(client).login(
                external_id=str(payload.external_id), otp=payload.otp
            )
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            try:
                detail = exc.response.json()
            except Exception:
                pass
            raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc

    lead = await session.scalar(select(Lead).where(Lead.external_id == payload.external_id))

    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        status=lead.status.value if lead else "unknown",
    )


@router.post("/refresh", response_model=RefreshResponse, summary="Renova tokens JWT")
async def refresh(payload: RefreshRequest):
    async with httpx.AsyncClient(
        base_url=settings.JWT_BASE_URL, timeout=settings.HTTP_TIMEOUT
    ) as client:
        try:
            tokens = await JwtClient(client).refresh_token(payload.refresh_token)
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            try:
                detail = exc.response.json()
            except Exception:
                pass
            raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc

    return RefreshResponse(**tokens)
