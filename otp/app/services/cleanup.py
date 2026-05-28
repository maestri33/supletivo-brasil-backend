"""Cleanup loop — purga OTPs antigos do banco.

Roda como task de fundo no lifespan do FastAPI. Intervalo e retenção
controlados via `.env`:
- OTP_CLEANUP_INTERVAL_S (default 3600s = 1h)
- OTP_CLEANUP_RETENTION_DAYS (default 30)

Limpa:
- otp.otp_logs com status terminal (verified, failed, expired) e
  created_at < now - retention_days.
- otp.pending_notify com status in (done, expired) e
  created_at < now - retention_days.
- otp.rate_limit com last_created_at < now - 1d (entradas órfãs).
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.config import get_settings
from app.db import async_session_maker
from app.models.otp import OTPLog
from app.models.pending_notify import PendingNotify
from app.models.rate_limit import RateLimit
from app.utils.logging import get_logger

log = get_logger(__name__)
settings = get_settings()

_TERMINAL_OTP_STATUSES = ("verified", "failed", "expired")
_TERMINAL_PENDING_STATUSES = ("done", "expired")


async def run_once() -> dict:
    """Executa uma rodada de cleanup. Retorna contagens removidas."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=settings.otp_cleanup_retention_days)
    rate_limit_cutoff = now - timedelta(days=1)

    async with async_session_maker() as session:
        logs_result = await session.execute(
            delete(OTPLog).where(
                OTPLog.status.in_(_TERMINAL_OTP_STATUSES),
                OTPLog.created_at < cutoff,
            )
        )
        pending_result = await session.execute(
            delete(PendingNotify).where(
                PendingNotify.status.in_(_TERMINAL_PENDING_STATUSES),
                PendingNotify.created_at < cutoff,
            )
        )
        rl_result = await session.execute(
            delete(RateLimit).where(RateLimit.last_created_at < rate_limit_cutoff)
        )
        await session.commit()

    deleted = {
        "otp_logs": logs_result.rowcount or 0,
        "pending_notify": pending_result.rowcount or 0,
        "rate_limit": rl_result.rowcount or 0,
    }
    log.info("otp.cleanup.run", **deleted, cutoff=cutoff.isoformat())
    return deleted


async def cleanup_loop(stop: asyncio.Event) -> None:
    """Loop infinito. Para quando stop_event é setado."""
    interval_s = settings.otp_cleanup_interval_s
    log.info("otp.cleanup.loop.start", interval_s=interval_s)
    while not stop.is_set():
        try:
            await run_once()
        except Exception as exc:
            log.error("otp.cleanup.loop.error", error=str(exc))
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_s)
        except TimeoutError:
            pass
    log.info("otp.cleanup.loop.stop")
