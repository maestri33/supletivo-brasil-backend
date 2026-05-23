"""Endpoint de verificacao — consulta CPF/phone e dispara OTP se encontrado."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel

from app.exceptions import IntegrationError, ValidationError
from app.integrations.notify import NotifyClient, NotifyError
from app.integrations.otp import OTPClient
from app.integrations.profiles import ProfilesClient, ProfilesError
from app.utils.validation import validate_cpf, validate_phone

router = APIRouter(prefix="/check", tags=["check"])

OTP_RATELIMIT_SECONDS = 30
OTP_KEY_PREFIX = "otp:ratelimit:"


class CheckRequest(BaseModel):
    cpf: str | None = None
    phone: str | None = None
    external_id: str | None = None


@router.post("", summary="Verifica CPF, phone ou external_id e dispara OTP se encontrado")
async def check(data: CheckRequest, bg: BackgroundTasks, request: Request) -> dict:
    redis = getattr(request.app.state, "redis", None)
    if data.external_id:
        return await _check_external_id(data.external_id, bg, redis)
    if data.cpf:
        try:
            validate_cpf(data.cpf)
        except ValueError as exc:
            raise ValidationError(str(exc), code="CPF_INVALID")
        return await _check_cpf(data.cpf, bg, redis)
    if data.phone:
        try:
            validate_phone(data.phone)
        except ValueError as exc:
            raise ValidationError(str(exc), code="PHONE_INVALID")
        return await _check_phone(data.phone, bg, redis)
    raise ValidationError("Informe cpf, phone ou external_id.", code="MISSING_FIELD")


# ── Reusable lookups ──────────────────────────────


async def lookup_cpf(cpf: str) -> dict:
    """Consulta CPF via Profiles. Retorna {found, valid, external_id?}."""
    try:
        async with ProfilesClient() as profiles:
            return await profiles.check_cpf(cpf)
    except ProfilesError as exc:
        if 400 <= exc.status < 500:
            raise ValidationError(str(exc.detail), code="PROFILES_ERROR")
        raise IntegrationError(
            f"Servico de validacao de CPF indisponivel: {exc.detail}",
            code="PROFILES_UNAVAILABLE",
        )


async def lookup_phone(phone: str) -> dict:
    """Consulta phone via Notify. Retorna {found, external_id?, phone_valid?, ...}."""
    try:
        async with NotifyClient() as notify:
            return await notify.check_contact(phone=phone)
    except NotifyError as exc:
        if 400 <= exc.status < 500:
            raise ValidationError(str(exc.detail), code="NOTIFY_ERROR")
        raise IntegrationError(
            f"Servico de validacao de phone indisponivel: {exc.detail}",
            code="NOTIFY_UNAVAILABLE",
        )


async def dispatch_otp(external_id: str) -> None:
    """Dispara OTP em background — nao bloqueia o fluxo em caso de falha."""
    try:
        async with OTPClient(timeout=5) as otp:
            await otp.create(external_id)
    except Exception:
        pass


# ── Rate limit ────────────────────────────────────


async def try_acquire_otp_slot(redis, external_id: str) -> int | None:
    """Tenta adquirir slot de OTP. Retorna None se ok, ou segundos restantes se bloqueado."""
    if redis is None:
        return None  # sem Redis, permite sempre
    key = f"{OTP_KEY_PREFIX}{external_id}"
    acquired = await redis.set(key, "1", nx=True, ex=OTP_RATELIMIT_SECONDS)
    if acquired:
        return None
    ttl = await redis.ttl(key)
    return max(ttl, 0)


async def lookup_external_id(external_id: str) -> dict:
    """Busca dados completos: Profiles (cpf) + Notify (phone). Retorna {found, external_id, cpf?, phone?}."""
    result: dict = {"external_id": external_id}
    try:
        async with ProfilesClient() as profiles:
            profile = await profiles.get_one(external_id)
            result["cpf"] = profile.get("cpf")
    except ProfilesError:
        pass

    try:
        async with NotifyClient() as notify:
            contact = await notify.get_contact(external_id)
            result["phone"] = contact.get("phone")
    except NotifyError:
        pass

    result["found"] = "cpf" in result or "phone" in result
    return result


# ── Internal ──────────────────────────────────────


async def _check_external_id(external_id: str, bg: BackgroundTasks, redis) -> dict:
    result = await lookup_external_id(external_id)
    if result["found"]:
        wait = await try_acquire_otp_slot(redis, external_id)
        if wait is not None:
            result["otp_wait"] = wait
            return result
        bg.add_task(dispatch_otp, external_id)
        return result
    return result


async def _check_cpf(cpf: str, bg: BackgroundTasks, redis) -> dict:
    result = await lookup_cpf(cpf)
    if result["found"]:
        external_id = result["external_id"]
        wait = await try_acquire_otp_slot(redis, external_id)
        if wait is not None:
            return {"found": True, "external_id": external_id, "otp_wait": wait}
        bg.add_task(dispatch_otp, external_id)
        return {"found": True, "external_id": external_id}
    return {"found": False, "valid": result.get("valid", False)}


async def _check_phone(phone: str, bg: BackgroundTasks, redis) -> dict:
    result = await lookup_phone(phone)
    if result["found"]:
        external_id = result["external_id"]
        wait = await try_acquire_otp_slot(redis, external_id)
        if wait is not None:
            return {"found": True, "external_id": external_id, "otp_wait": wait}
        bg.add_task(dispatch_otp, external_id)
        return {"found": True, "external_id": external_id}
    return {"found": False, "valid": result.get("phone_valid", False)}
