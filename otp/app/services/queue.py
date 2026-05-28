"""Processador da fila de retry do notify (SQLAlchemy 2)."""

import asyncio
import fcntl
import os
from datetime import UTC, datetime

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session_maker
from app.models.otp import OTPLog
from app.models.pending_notify import PendingNotify
from app.services import notify
from app.utils.logging import get_logger

log = get_logger(__name__)
settings = get_settings()

_INTERVAL_S = 5
_MAX_ATTEMPTS = 5
_BACKOFF_S = [5, 10, 20, 40]
_LOCK_PATH = "/tmp/otp_queue.lock"


def _backoff(attempts: int) -> int:
    idx = min(attempts, len(_BACKOFF_S)) - 1
    return _BACKOFF_S[idx] if idx >= 0 else _BACKOFF_S[0]


async def _process_one(
    session: AsyncSession,
    http: httpx.AsyncClient,
    entry: PendingNotify,
) -> None:
    now = datetime.now(UTC)
    age_s = (now - entry.created_at).total_seconds()

    if age_s > settings.otp_ttl_s:
        entry.status = "expired"
        entry.error_detail = "OTP expirado antes do reenvio"
        await session.execute(
            update(OTPLog)
            .where(OTPLog.id == entry.otp_log_id)
            .values(
                status="failed",
                failure_reason="notify_down",
                error_detail="OTP expirado — notify indisponível",
            )
        )
        await session.commit()
        log.info("queue.expired", id=entry.id, otp_log_id=entry.otp_log_id)
        return

    entry.attempts += 1
    entry.next_retry_at = datetime.fromtimestamp(now.timestamp() + 3600, tz=UTC)
    await session.commit()

    try:
        result = await notify.send_message(
            http,
            external_id=str(entry.external_id),
            content=entry.content,
        )
    except Exception as exc:
        entry.error_detail = str(exc)
        if entry.attempts >= _MAX_ATTEMPTS:
            entry.status = "expired"
            await session.execute(
                update(OTPLog)
                .where(OTPLog.id == entry.otp_log_id)
                .values(
                    status="failed",
                    failure_reason="notify_down",
                    error_detail=f"Esgotadas {_MAX_ATTEMPTS} tentativas: {exc}",
                )
            )
            await session.commit()
            log.info(
                "queue.max_attempts",
                id=entry.id,
                otp_log_id=entry.otp_log_id,
                attempts=entry.attempts,
            )
        else:
            backoff_s = _backoff(entry.attempts)
            entry.next_retry_at = datetime.fromtimestamp(
                datetime.now(UTC).timestamp() + backoff_s,
                tz=UTC,
            )
            await session.commit()
            log.info(
                "queue.retry_scheduled",
                id=entry.id,
                attempts=entry.attempts,
                next_retry_at=entry.next_retry_at.isoformat(),
            )
        return

    entry.status = "done"
    await session.execute(
        update(OTPLog)
        .where(OTPLog.id == entry.otp_log_id)
        .values(status="sent", message_id=result.get("id"))
    )
    await session.commit()
    log.info(
        "queue.sent",
        id=entry.id,
        otp_log_id=entry.otp_log_id,
        message_id=result.get("id"),
    )


async def process_pending(http: httpx.AsyncClient) -> None:
    now = datetime.now(UTC)
    async with async_session_maker() as session:
        pending = await session.scalars(
            select(PendingNotify)
            .where(PendingNotify.status == "pending", PendingNotify.next_retry_at <= now)
            .limit(20)
        )
        for entry in pending.all():
            await _process_one(session, http, entry)


async def queue_loop(http: httpx.AsyncClient, stop: asyncio.Event) -> None:
    log.info("queue.loop.start", interval_s=_INTERVAL_S)
    lock_fd = open(_LOCK_PATH, "w")  # noqa: ASYNC230 — flock requires fd
    while not stop.is_set():
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                await process_pending(http)
            except Exception as exc:
                log.error("queue.loop.error", error=str(exc))
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except BlockingIOError:
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=_INTERVAL_S)
        except TimeoutError:
            pass
    lock_fd.close()
    try:
        os.unlink(_LOCK_PATH)
    except FileNotFoundError:
        pass
    log.info("queue.loop.stop")
