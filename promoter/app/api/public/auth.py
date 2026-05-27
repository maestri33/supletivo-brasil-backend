"""Rotas publicas (EXPOSTAS): check/login/refresh.

Promoter nao se auto-registra (criado pelo coordinator), entao nao ha' /register.
Superficie publica (CONVENTION §5): nada de logica de dominio aqui — valida
entrada, chama o service e devolve o schema.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.db import get_session
from app.schemas.auth import (
    CheckRequest,
    CheckResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
)
from app.services import auth as auth_svc

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.post("/check", response_model=CheckResponse, summary="Verifica usuario e dispara OTP")
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
