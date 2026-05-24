"""Fila de saida (outbound_jobs): reenvia eventos internos com retry exponencial.

Caminho do dinheiro: `enqueue` insere o job na sessao do caller, entao ele commita
junto com o estado durável (ex.: checkout marcado pago) — atomico. A entrega fica a
cargo do worker (`process_due`), que faz claim atomico antes de cada POST para nao
duplicar entrega entre instancias (API + worker dedicado podem rodar em paralelo).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session_maker
from app.models import OutboundJob

logger = structlog.get_logger("infinitepay")

BACKOFF_SECONDS = [60, 300, 1800, 7200, 43200, 86400]


def _now() -> datetime:
    return datetime.now(UTC)


async def _deliver_payload(url: str, payload: dict) -> tuple[bool, str | None, int | None]:
    try:
        async with httpx.AsyncClient(timeout=get_settings().http_timeout) as client:
            r = await client.post(url, json=payload)
        if 200 <= r.status_code < 300:
            return True, None, r.status_code
        return False, f"HTTP {r.status_code}: {r.text[:300]}", r.status_code
    except Exception as e:  # noqa: BLE001 — qualquer falha de transporte vira retry
        return False, f"{type(e).__name__}: {e}", None


async def enqueue(
    db: AsyncSession, *, url: str, payload: dict, external_id: str | None = None
) -> str:
    """Insere um job na sessao do caller (commit fica com o caller — atomico)."""
    job = OutboundJob(
        url=url,
        payload=payload,
        external_id=external_id,
        max_attempts=len(BACKOFF_SECONDS) + 1,
    )
    db.add(job)
    await db.flush()
    return job.id


async def process_due(limit: int = 20) -> int:
    """Entrega jobs vencidos. Claim atomico (commit) antes do POST evita duplicar."""
    async with async_session_maker() as s:
        stmt = (
            select(
                OutboundJob.id,
                OutboundJob.url,
                OutboundJob.payload,
                OutboundJob.attempts,
                OutboundJob.max_attempts,
            )
            .where(OutboundJob.delivered_at.is_(None))
            .where(OutboundJob.next_attempt_at <= _now())
            .order_by(OutboundJob.next_attempt_at)
            .limit(limit)
        )
        jobs = (await s.execute(stmt)).all()

    processed = 0
    for job_id, url, payload, attempts, max_attempts in jobs:
        async with async_session_maker() as s:
            result = await s.execute(
                update(OutboundJob)
                .where(OutboundJob.id == job_id)
                .where(OutboundJob.next_attempt_at <= _now())
                .where(OutboundJob.delivered_at.is_(None))
                .values(next_attempt_at=_now() + timedelta(seconds=30))
            )
            await s.commit()
            locked = result.rowcount == 1

        if not locked:
            continue

        ok, err, _status = await _deliver_payload(url, payload)
        attempts += 1

        async with async_session_maker() as s:
            job = await s.get(OutboundJob, job_id)
            if job is None or job.delivered_at is not None:
                continue
            job.attempts = attempts
            if ok:
                job.delivered_at = _now()
                job.last_error = None
            else:
                job.last_error = err
                if attempts >= max_attempts:
                    job.next_attempt_at = _now() + timedelta(days=365)
                else:
                    delay = BACKOFF_SECONDS[min(attempts - 1, len(BACKOFF_SECONDS) - 1)]
                    job.next_attempt_at = _now() + timedelta(seconds=delay)
            await s.commit()
        processed += 1
    return processed


async def cleanup_old_jobs(days: int = 30) -> int:
    cutoff = _now() - timedelta(days=days)
    async with async_session_maker() as s:
        result = await s.execute(
            delete(OutboundJob)
            .where(OutboundJob.delivered_at.is_(None))
            .where(OutboundJob.attempts >= OutboundJob.max_attempts)
            .where(OutboundJob.updated_at < cutoff)
        )
        await s.commit()
        return result.rowcount


async def run_worker_loop(stop_event: asyncio.Event | None = None) -> None:
    await cleanup_old_jobs()
    while True:
        if stop_event is not None and stop_event.is_set():
            return
        try:
            await process_due()
        except Exception:
            logger.exception("worker_loop_process_due_failed")
        await asyncio.sleep(get_settings().worker_poll_seconds)
