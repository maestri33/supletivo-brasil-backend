"""Endpoint de login — verifica role, valida OTP, emite JWT."""

from __future__ import annotations

from fastapi import APIRouter

from app.exceptions import ForbiddenError, UnauthorizedError
from app.integrations.jwt import JWTClient
from app.integrations.otp import OTPClient, OTPError
from app.integrations.roles import RolesClient
from app.schemas.auth import LoginRequest, TokenResponse
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/login", tags=["login"])


@router.post("", summary="Login — verifica role, valida OTP, emite JWT")
async def login(data: LoginRequest) -> TokenResponse:
    # 1. Busca roles e verifica se a pedida esta entre elas
    user_roles = await _get_roles(data.external_id)
    if data.role not in user_roles:
        logger.warning("login_role_denied", external_id=data.external_id, requested_role=data.role, available_roles=user_roles)
        raise ForbiddenError(
            f"Usuario nao possui a role '{data.role}'.",
            code="ROLE_NOT_HELD",
        )

    # 2. Verify OTP
    await _verify_otp(data.external_id, data.otp)

    # 3. Issue JWT com todas as roles ativas
    async with JWTClient() as jwt:
        tokens = await jwt.issue(data.external_id, user_roles)

    logger.info("login_success", external_id=data.external_id, role=data.role)

    return TokenResponse(**tokens)


# ── Reusable ──────────────────────────────────────


async def verify_role(external_id: str, role: str) -> None:
    """Verifica se o usuario possui determinada role ativa."""
    await _verify_role(external_id, role)


async def verify_otp(external_id: str, code: str) -> None:
    """Valida codigo OTP. Levanta UnauthorizedError se invalido."""
    await _verify_otp(external_id, code)


# ── Internal ──────────────────────────────────────


async def _get_roles(external_id: str) -> list[str]:
    """Busca todas as roles ativas do usuario no Roles Service."""
    async with RolesClient() as roles:
        result = await roles.get_roles(external_id)
    return result.get("roles", [])


async def _verify_role(external_id: str, role: str) -> None:
    user_roles = await _get_roles(external_id)
    if role not in user_roles:
        raise ForbiddenError(
            f"Usuario nao possui a role '{role}'.",
            code="ROLE_NOT_HELD",
        )


async def _verify_otp(external_id: str, code: str) -> None:
    try:
        async with OTPClient() as otp:
            result = await otp.check(external_id, code)
    except OTPError as exc:
        raise UnauthorizedError(f"Erro ao verificar OTP: {exc.detail}", code="OTP_ERROR")

    if not result.get("valid"):
        raise UnauthorizedError("OTP invalido ou expirado.", code="OTP_INVALID")
