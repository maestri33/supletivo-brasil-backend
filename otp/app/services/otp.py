"""OTP service — gera códigos, envia via notify, valida (SQLAlchemy 2)."""

import hashlib
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import NotifyPermanentError, NotifyTransientError
from app.models.otp import OTPLog
from app.models.pending_notify import PendingNotify
from app.services import notify
from app.services import rate_limit as rate_limit_service
from app.utils.logging import get_logger

log = get_logger(__name__)
settings = get_settings()

_TEMPLATE_PATH = Path(__file__).parent / "otp.md"


def generate_code(length: int | None = None) -> str:
    """Gera código numérico seguro."""
    n = length or settings.otp_num_digits
    return "".join(str(secrets.randbelow(10)) for _ in range(n))


def _hash_code(code: str) -> str:
    """SHA256 — o código em texto plano nunca é persistido."""
    return hashlib.sha256(code.encode()).hexdigest()


def _render_template(code: str, footer: str, ttl_minutos: int) -> str:
    raw = _TEMPLATE_PATH.read_text(encoding="utf-8")
    # {{rodape}} no template fica colado na ultima linha. Se footer e' vazio,
    # apenas remove o placeholder; se tem conteudo, prepende \n\n pra
    # separar do paragrafo anterior. Resultado: sem footer = mensagem
    # termina limpa, sem espaco trailing.
    rodape = f"\n\n{footer}" if footer else ""
    return (
        raw.replace("{{codigo}}", code)
        .replace("{{ttl_minutos}}", str(ttl_minutos))
        .replace("{{rodape}}", rodape)
        .rstrip()
        + "\n"
    )


async def generate_and_send(
    session: AsyncSession,
    http: httpx.AsyncClient,
    *,
    external_id: UUID,
) -> OTPLog:
    """Gera OTP, persiste, e envia mensagem via notify.

    Aplica rate limit ANTES de qualquer trabalho — se bloqueado, levanta
    RateLimitExceeded (handler global converte pra 429 com Retry-After).
    """
    if not settings.otp_active:
        log.warning("otp.generate.blocked", external_id=str(external_id))
        otp_log = OTPLog(
            external_id=external_id,
            code_hash="",
            status="failed",
            failure_reason="inactive",
            error_detail="Serviço OTP desativado na configuração",
        )
        session.add(otp_log)
        await session.commit()
        await session.refresh(otp_log)
        return otp_log

    # Rate limit (pode levantar RateLimitExceeded → 429)
    await rate_limit_service.check_and_record(session, external_id)

    log.info("otp.generate.requested", external_id=str(external_id))
    code = generate_code()

    otp_log = OTPLog(
        external_id=external_id,
        code_hash=_hash_code(code),
        status="generated",
    )
    session.add(otp_log)
    await session.commit()
    await session.refresh(otp_log)
    log.info("otp.generated", id=otp_log.id, external_id=str(external_id))

    ttl_minutos = settings.otp_ttl_s // 60
    content = _render_template(code, footer=settings.otp_footer, ttl_minutos=ttl_minutos)

    try:
        result = await notify.send_message(http, external_id=str(external_id), content=content)
        otp_log.status = "sent"
        otp_log.message_id = result.get("id")
        await session.commit()
        log.info("otp.sent", id=otp_log.id, message_id=otp_log.message_id)
    except NotifyPermanentError as exc:
        otp_log.status = "failed"
        otp_log.failure_reason = "notify_permanent"
        otp_log.error_detail = str(exc)
        await session.commit()
        log.error("otp.send_failed", id=otp_log.id, error=str(exc))
    except NotifyTransientError as exc:
        pending = PendingNotify(
            external_id=external_id,
            content=content,
            otp_log_id=otp_log.id,
            attempts=1,
            next_retry_at=datetime.now(UTC),
            error_detail=str(exc),
        )
        session.add(pending)
        await session.commit()
        log.info("otp.queued", id=otp_log.id, external_id=str(external_id))

    return otp_log


async def verify_code(
    session: AsyncSession,
    http: httpx.AsyncClient,
    *,
    external_id: UUID,
    code: str,
) -> dict:
    """Valida código OTP. Retorna {'valid': bool, 'detail': str}.

    Cada tentativa errada incrementa OTPLog.attempts. Quando atinge
    OTP_MAX_ATTEMPTS, o OTP é invalidado (status=failed, failure_reason=invalid_code).
    """
    if not settings.otp_active:
        log.warning("otp.verify.blocked", external_id=str(external_id))
        return {"valid": False, "detail": "Serviço OTP desativado"}

    log.info("otp.verify.requested", external_id=str(external_id))

    otp_log = await session.scalar(
        select(OTPLog)
        .where(OTPLog.external_id == external_id, OTPLog.status.in_(["generated", "sent"]))
        .order_by(OTPLog.created_at.desc())
        .limit(1)
    )

    if otp_log is None:
        log.info("otp.check.no_pending_otp", external_id=str(external_id))
        return {"valid": False, "detail": "Nenhum OTP pendente encontrado"}

    age_s = time.time() - otp_log.created_at.timestamp()
    if age_s > settings.otp_ttl_s:
        otp_log.status = "expired"
        otp_log.failure_reason = "expired"
        await session.commit()
        log.info("otp.check.expired", id=otp_log.id, age_s=age_s)
        return {"valid": False, "detail": "OTP expirado"}

    if not secrets.compare_digest(otp_log.code_hash, _hash_code(code)):
        otp_log.attempts += 1
        if otp_log.attempts >= settings.otp_max_attempts:
            otp_log.status = "failed"
            otp_log.failure_reason = "invalid_code"
            otp_log.error_detail = f"Esgotadas {settings.otp_max_attempts} tentativas"
            await session.commit()
            log.info(
                "otp.check.max_attempts",
                id=otp_log.id,
                attempts=otp_log.attempts,
            )
            return {
                "valid": False,
                "detail": f"OTP invalidado após {settings.otp_max_attempts} tentativas",
            }
        await session.commit()
        log.info("otp.check.invalid_code", id=otp_log.id, attempts=otp_log.attempts)
        return {"valid": False, "detail": "Código inválido"}

    otp_log.status = "verified"
    otp_log.verified_at = datetime.now(UTC)
    await session.commit()
    log.info("otp.check.verified", id=otp_log.id, external_id=str(external_id))
    return {"valid": True, "detail": "ok"}


async def list_logs(
    session: AsyncSession,
    *,
    external_id: UUID | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[OTPLog]:
    stmt = select(OTPLog)
    if external_id:
        stmt = stmt.where(OTPLog.external_id == external_id)
    if status:
        stmt = stmt.where(OTPLog.status == status)
    stmt = stmt.order_by(OTPLog.created_at.desc()).offset(offset).limit(limit)
    result = await session.scalars(stmt)
    return list(result.all())
