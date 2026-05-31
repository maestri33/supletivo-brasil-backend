"""Rotas publicas (EXPOSTAS): check/register/login/refresh.

Superficie publica (CONVENTION §5): nada de logica de dominio aqui — valida
entrada, chama o service e devolve o schema.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.config import get_settings
from app.db import get_session
from app.schemas.auth import (
    CheckRequest,
    CheckResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.services import auth as auth_svc
from app.services import notifications

settings = get_settings()

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.post("/check", response_model=CheckResponse, summary="Verifica candidato e dispara OTP")
async def check(payload: CheckRequest):
    if not any([payload.cpf, payload.phone, payload.external_id]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="cpf, phone ou external_id obrigatorio",
        )
    with upstream_errors():
        return await auth_svc.check(
            cpf=payload.cpf,
            phone=payload.phone,
            external_id=str(payload.external_id) if payload.external_id else None,
        )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra novo candidato",
)
async def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    hub_external_id = (
        str(payload.hub_external_id) if payload.hub_external_id else settings.hub_default
    )
    with upstream_errors():
        external_id, created = await auth_svc.register(
            session,
            phone=payload.phone,
            cpf=payload.cpf,
            hub_external_id=hub_external_id,
        )
    await session.commit()

    if created:
        background_tasks.add_task(
            notifications.notify_captured, external_id, payload.phone, hub_external_id
        )

    return RegisterResponse(external_id=external_id, message="Cadastro realizado. OTP enviado.")


@router.post("/login", response_model=LoginResponse, summary="Valida OTP e gera JWT")
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)):
    with upstream_errors():
        result = await auth_svc.login(
            session, external_id=str(payload.external_id), otp=payload.otp
        )
    return LoginResponse(**result)


@router.post("/refresh", response_model=RefreshResponse, summary="Renova tokens JWT")
async def refresh(payload: RefreshRequest):
    with upstream_errors():
        tokens = await auth_svc.refresh(refresh_token=payload.refresh_token)
    return RefreshResponse(**tokens)
