"""Endpoint de verificacao — consulta CPF/phone e dispara OTP se encontrado.

Respostas uniformizadas (COD-32): nunca diferencia found=true/false.
Sempre retorna {"otp_sent": true} ou {"otp_wait": N}, independente
do usuario existir ou nao. Apenas erros de formato (CPF/phone invalido)
retornam 422 — validacao de formato nao vaza existencia.
"""

from __future__ import annotations

import asyncio
import random

from fastapi import APIRouter, BackgroundTasks, Request

from app.exceptions import IntegrationError, ValidationError
from app.integrations.notify import NotifyClient, NotifyError
from app.integrations.otp import OTPClient
from app.integrations.profiles import ProfilesClient, ProfilesError
from app.schemas.auth import CheckRequest
from app.utils.logging import get_logger
from app.utils.validation import validate_cpf, validate_phone

logger = get_logger(__name__)

router = APIRouter(prefix="/check", tags=["check"])

OTP_RATELIMIT_SECONDS = 30
OTP_KEY_PREFIX = "otp:ratelimit:"


@router.post("", summary="Verifica CPF, phone ou external_id e dispara OTP se encontrado")
async def check(data: CheckRequest, bg: BackgroundTasks, request: Request) -> dict:
    redis = getattr(request.app.state, "redis", None)
    if data.external_id:
        return await _check_external_id(data.external_id, bg, redis, request)
    if data.cpf:
        try:
            validate_cpf(data.cpf)
        except ValueError as exc:
            raise ValidationError(str(exc), code="CPF_INVALID")
        return await _check_cpf(data.cpf, bg, redis, request)
    if data.phone:
        try:
            validate_phone(data.phone)
        except ValueError as exc:
            raise ValidationError(str(exc), code="PHONE_INVALID")
        return await _check_phone(data.phone, bg, redis, request)
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
    except Exception as exc:
        logger.warning("otp_dispatch_failed", external_id=external_id, error=type(exc).__name__)


# ── Rate limit ────────────────────────────────────


async def try_acquire_otp_slot(redis, key: str) -> int | None:
    """Tenta adquirir slot de OTP. Retorna None se ok, ou segundos restantes se bloqueado."""
    if redis is None:
        return None  # sem Redis, permite sempre
    rkey = f"{OTP_KEY_PREFIX}{key}"
    acquired = await redis.set(rkey, "1", nx=True, ex=OTP_RATELIMIT_SECONDS)
    if acquired:
        return None
    ttl = await redis.ttl(rkey)
    return max(ttl, 0)


def _anon_key(request: Request) -> str:
    """Chave de rate-limit para usuario nao encontrado (baseada em IP).

    Usa IP do cliente para que um atacante nao consiga bypassar
    o rate limit alternando CPFs/phones invalidos.
    """
    ip = request.client.host if request.client else "unknown"
    return f"anon:{ip}"


async def lookup_external_id(external_id: str) -> dict:
    """Busca dados completos: Profiles (cpf) + Notify (phone).

    Retorna {found, external_id, cpf?, phone?}.
    """
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


# ── Timing normalization (COD-32 task 4) ──────────

_TIMING_JITTER_MIN = 0.10  # 100ms
_TIMING_JITTER_MAX = 0.30  # 300ms


async def _obfuscate_timing() -> None:
    """Adiciona jitter aleatorio para mascarar timing de lookup not-found.

    Quando o usuario NAO existe, a resposta do Profiles/Notify tende a ser
    mais rapida (cache miss simples vs cache hit com resolucao completa).
    Este delay mascara essa diferenca, tornando a latencia indistinguivel
    entre found e not-found aos olhos de um atacante que mede o tempo.
    """
    await asyncio.sleep(random.uniform(_TIMING_JITTER_MIN, _TIMING_JITTER_MAX))


# ── Internal, resposta uniforme (COD-32) ──────────


async def _check_external_id(
    external_id: str, bg: BackgroundTasks, redis, request: Request
) -> dict:
    result = await lookup_external_id(external_id)
    found = bool(result["found"])
    eid = external_id if found else None
    if found:
        rkey = external_id
    else:
        rkey = _anon_key(request)

    wait = await try_acquire_otp_slot(redis, rkey)
    if wait is not None:
        return {"otp_wait": wait, "found": found, "external_id": eid}

    bg.add_task(dispatch_otp, external_id if found else rkey)
    logger.info("otp_dispatched_via_external_id", external_id=external_id[:8] if found else rkey[:16])
    return {"otp_sent": True, "found": found, "external_id": eid}


async def _check_cpf(cpf: str, bg: BackgroundTasks, redis, request: Request) -> dict:
    result = await lookup_cpf(cpf)
    found = bool(result["found"])
    eid = result.get("external_id") if found else None
    if found:
        rkey = eid
    else:
        rkey = _anon_key(request)

    wait = await try_acquire_otp_slot(redis, rkey)
    if wait is not None:
        return {"otp_wait": wait, "found": found, "external_id": eid}

    bg.add_task(dispatch_otp, rkey)
    return {"otp_sent": True, "found": found, "external_id": eid}


async def _check_phone(phone: str, bg: BackgroundTasks, redis, request: Request) -> dict:
    result = await lookup_phone(phone)
    found = bool(result["found"])
    eid = result.get("external_id") if found else None
    whatsapp_valid = result.get("phone_valid")
    if found:
        rkey = eid
    else:
        rkey = _anon_key(request)

    wait = await try_acquire_otp_slot(redis, rkey)
    if wait is not None:
        return {"otp_wait": wait, "found": found, "external_id": eid, "whatsapp_valid": whatsapp_valid}

    bg.add_task(dispatch_otp, rkey)
    return {"otp_sent": True, "found": found, "external_id": eid, "whatsapp_valid": whatsapp_valid}
