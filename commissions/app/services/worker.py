"""Worker — loop unico de fundo do commissions-service.

A cada `payout_poll_seconds`:
  1. empurra/reconcilia os Payouts pendentes (services/payout.process_due_payouts);
  2. na SEXTA, a partir de `processing_cron_hour` (18h America/Sao_Paulo), dispara o
     lote semanal UMA vez (idempotente por semana, no DB e tambem por _last_batch_week).

Nada dispara dinheiro so por o servico subir: o lote so roda na janela de sexta, e o
push de payout so acontece se houver Payout QUEUED. (dev usa Asaas REAL — Pix de verdade.)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.db import async_session_maker
from app.services.commissions import process_weekly_batch
from app.services.payout import process_due_payouts
from app.utils.logging import get_logger

BR_TZ = ZoneInfo("America/Sao_Paulo")
logger = get_logger("commissions.worker")

_FRIDAY = 4  # Monday=0 ... Friday=4


async def worker_loop() -> None:
    settings = get_settings()
    logger.info(
        "worker.started",
        timezone=settings.processing_cron_timezone,
        cron_hour=settings.processing_cron_hour,
        poll_seconds=settings.payout_poll_seconds,
    )
    last_batch_week: str | None = None

    while True:
        try:
            # 1) Move os payouts (push dos QUEUED + reconciliacao dos em voo).
            n = await process_due_payouts()
            if n:
                logger.info("worker.payouts_processed", count=n)

            # 2) Lote semanal: sexta, a partir da hora configurada, uma vez por semana.
            now = datetime.now(BR_TZ)
            week_monday = (now.date() - timedelta(days=now.weekday())).isoformat()
            if (
                now.weekday() == _FRIDAY
                and now.hour >= settings.processing_cron_hour
                and last_batch_week != week_monday
            ):
                logger.info("worker.weekly_trigger", week_of=week_monday)
                async with async_session_maker() as s:
                    batch = await process_weekly_batch(s, week_of=week_monday)
                    await s.commit()
                last_batch_week = week_monday
                if batch is not None:
                    logger.info(
                        "worker.weekly_done",
                        batch_id=batch.id,
                        week_of=batch.week_of,
                        total_cents=batch.total_cents,
                        bonus_cents=batch.bonus_cents,
                    )

        except asyncio.CancelledError:
            logger.info("worker.cancelled")
            raise
        except Exception:
            logger.exception("worker.error")

        await asyncio.sleep(settings.payout_poll_seconds)
