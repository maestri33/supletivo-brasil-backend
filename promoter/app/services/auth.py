"""Rotas publicas de autenticacao — delega identidade ao `auth` e tokens ao `jwt`.

O promoter nao se auto-registra (e' criado pelo coordinator). Aqui so' ha'
check/login/refresh. O login le o status local do promoter para devolver junto.
"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.auth import AuthClient
from app.integrations.jwt import JwtClient
from app.services import promoter as promoter_svc

settings = get_settings()


async def check(*, cpf: str | None, phone: str | None, external_id: str | None) -> dict:
    async with httpx.AsyncClient(
        base_url=settings.auth_base_url, timeout=settings.http_timeout
    ) as client:
        return await AuthClient(client).check(cpf=cpf, phone=phone, external_id=external_id)


async def login(session: AsyncSession, *, external_id: str, otp: str) -> dict:
    async with httpx.AsyncClient(
        base_url=settings.auth_base_url, timeout=settings.http_timeout
    ) as client:
        tokens = await AuthClient(client).login(external_id=external_id, otp=otp)

    promoter = await promoter_svc.get(session, external_id)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
        "status": promoter.status if promoter else "unknown",
    }


async def refresh(*, refresh_token: str) -> dict:
    async with httpx.AsyncClient(
        base_url=settings.jwt_base_url, timeout=settings.http_timeout
    ) as client:
        return await JwtClient(client).refresh_token(refresh_token)
