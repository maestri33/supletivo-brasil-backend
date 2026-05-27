"""Worker loop — asyncio background task for weekly batch processing.

Runs continuously during the service lifespan and schedules batch processing
for Fridays at 18:00 America/Sao_Paulo. Also provides a trigger endpoint
for manual processing.

Idempotency: the worker checks if a batch already exists for the current week
before creating a new one. Running twice in the same window will not duplicate.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from app.config import get_settings
from app.db import async_session_maker
from app.models.payment_batch import PaymentBatchStatus
from app.services.payment_batch_service import PaymentBatchService, _get_current_week_monday
from app.utils.logging import get_logger

logger = get_logger("commissions.worker")


async def worker_loop() -> None:
    """Background worker that processes weekly batches on schedule.

    Runs on Friday at configured hour (default 18:00) in America/Sao_Paulo.
    Between scheduled runs, sleeps and checks periodically.
    """
    settings = get_settings()
    logger.info(
        "worker.started",
        timezone=settings.processing_cron_timezone,
        hour=settings.processing_cron_hour,
    )

    while True:
        try:
            now = _get_current_time()
            next_run = _calculate_next_friday(now, settings.processing_cron_hour)

            sleep_seconds = (next_run - now).total_seconds()
            if sleep_seconds > 0:
                logger.info(
                    "worker.next_run",
                    next_run=next_run.isoformat(),
                    sleep_hours=round(sleep_seconds / 3600, 1),
                )
                await asyncio.sleep(min(sleep_seconds, 3600))  # Wake hourly to check
                continue

            # Time to process
            week_of = _get_current_week_monday()
            logger.info("worker.processing_batch", week_of=week_of)

            async with async_session_maker() as session:
                service = PaymentBatchService(session)
                batch = await service.process_weekly_batch(week_of)

                logger.info(
                    "worker.batch_completed",
                    batch_id=batch.id,
                    week_of=batch.week_of,
                    total_cents=batch.total_cents,
                    status=batch.status.value,
                )

            # Sleep 24h after successful run to avoid double-trigger
            await asyncio.sleep(86400)

        except asyncio.CancelledError:
            logger.info("worker.cancelled")
            break
        except Exception:
            logger.exception("worker.error")
            await asyncio.sleep(300)  # Back off 5 min on error


async def trigger_manual_processing(week_of: str | None = None) -> dict:
    """Manually trigger batch processing (for API endpoint + admin use).

    Args:
        week_of: ISO Monday date. If None, calculates from current time.

    Returns:
        Dict with processing result info.
    """
    if week_of is None:
        week_of = _get_current_week_monday()

    logger.info("worker.manual_trigger", week_of=week_of)

    async with async_session_maker() as session:
        service = PaymentBatchService(session)
        batch = await service.process_weekly_batch(week_of)

        return {
            "success": batch.status == PaymentBatchStatus.COMPLETED,
            "payment_batch_id": batch.id,
            "message": (
                f"Batch {batch.id} for week {week_of}: {batch.status.value}"
                f" — total={batch.total_cents}c, bonus={batch.bonus_cents}c"
            ),
            "total_cents": batch.total_cents,
            "bonus_cents": batch.bonus_cents,
            "status": batch.status.value,
        }


def _get_current_time() -> datetime:
    """Get the current time in America/Sao_Paulo."""
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("America/Sao_Paulo"))


def _calculate_next_friday(now: datetime, target_hour: int) -> datetime:
    """Calculate the next Friday at target_hour in America/Sao_Paulo.

    If today is Friday and it's before target_hour, the next Friday is today.
    Otherwise, advance to next Friday.
    """
    days_ahead = (4 - now.weekday()) % 7  # Friday = 4
    if days_ahead == 0 and now.hour >= target_hour:
        days_ahead = 7  # Past today's target, go to next Friday

    next_date = now.date() + timedelta(days=days_ahead)
    return datetime(
        year=next_date.year,
        month=next_date.month,
        day=next_date.day,
        hour=target_hour,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=now.tzinfo,
    )
