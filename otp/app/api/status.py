"""Status endpoint — GET /status (SQLAlchemy 2)."""

import time
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models.otp import OTPLog
from app.models.rate_limit import RateLimit

router = APIRouter()
settings = get_settings()
_STARTED_AT = time.time()

_FAILED_STATUSES = ("failed", "expired")


def _uptime_s() -> int:
    return int(time.time() - _STARTED_AT)


async def _db_status(session: AsyncSession) -> dict:
    try:
        await session.execute(text("SELECT 1"))
        return {"ok": True, "detail": "conectado"}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}


async def _notify_status(http: httpx.AsyncClient) -> dict:
    try:
        resp = await http.get(f"{settings.notify_base_url}/health", timeout=5)
        return {
            "ok": resp.status_code == 200,
            "detail": resp.json().get("service", str(resp.status_code)),
        }
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}


async def _avg_verification_ms(session: AsyncSession) -> float | None:
    """Tempo médio (ms) entre created_at e verified_at para OTPs verificados."""
    avg_seconds = await session.scalar(
        select(
            func.avg(
                func.extract("epoch", OTPLog.verified_at) - func.extract("epoch", OTPLog.created_at)
            )
        ).where(OTPLog.status == "verified", OTPLog.verified_at.is_not(None))
    )
    if avg_seconds is None:
        return None
    return round(float(avg_seconds) * 1000, 2)


async def _failure_breakdown(session: AsyncSession) -> dict[str, int]:
    """Contagem de falhas agrupada por failure_reason."""
    rows = await session.execute(
        select(OTPLog.failure_reason, func.count(OTPLog.id))
        .where(OTPLog.status.in_(_FAILED_STATUSES))
        .group_by(OTPLog.failure_reason)
    )
    breakdown: dict[str, int] = {}
    for reason, cnt in rows.all():
        key = reason or "unspecified"
        breakdown[key] = cnt
    return breakdown


async def _top_failed_external_ids(session: AsyncSession, limit: int = 10) -> list[dict]:
    """Top N external_ids por número de OTPs com falha."""
    rows = await session.execute(
        select(OTPLog.external_id, func.count(OTPLog.id).label("fails"))
        .where(OTPLog.status.in_(_FAILED_STATUSES))
        .group_by(OTPLog.external_id)
        .order_by(func.count(OTPLog.id).desc())
        .limit(limit)
    )
    return [{"external_id": str(eid), "fails": fails} for eid, fails in rows.all()]


async def _rate_limit_active(session: AsyncSession) -> int:
    """Quantos external_ids tiveram OTP nos últimos 60s (estão em janela curta)."""
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.otp_ratelimit_window_s)
    result = await session.scalar(
        select(func.count(RateLimit.external_id)).where(RateLimit.last_created_at >= cutoff)
    )
    return int(result or 0)


@router.get("/status")
async def status(session: AsyncSession = Depends(get_session)) -> dict:  # noqa: B008
    db = await _db_status(session)

    async with httpx.AsyncClient(timeout=5) as http:
        notify = await _notify_status(http)

    by_status_rows = await session.execute(
        select(OTPLog.status, func.count(OTPLog.id)).group_by(OTPLog.status)
    )
    by_status = {"generated": 0, "sent": 0, "verified": 0, "failed": 0, "expired": 0}
    total = 0
    for st, cnt in by_status_rows.all():
        if st in by_status:
            by_status[st] = cnt
        total += cnt

    avg_verification_ms = await _avg_verification_ms(session)
    failure_breakdown = await _failure_breakdown(session)
    top_failed = await _top_failed_external_ids(session)
    rl_active = await _rate_limit_active(session)

    recent = await session.scalars(select(OTPLog).order_by(OTPLog.created_at.desc()).limit(10))

    return {
        "service": settings.service_name,
        "env": settings.env,
        "uptime_s": _uptime_s(),
        "config": {
            "footer": settings.otp_footer,
            "ttl_s": settings.otp_ttl_s,
            "num_digits": settings.otp_num_digits,
            "max_attempts": settings.otp_max_attempts,
            "active": settings.otp_active,
            "ratelimit_window_s": settings.otp_ratelimit_window_s,
            "ratelimit_hourly_max": settings.otp_ratelimit_hourly_max,
            "cleanup_interval_s": settings.otp_cleanup_interval_s,
            "cleanup_retention_days": settings.otp_cleanup_retention_days,
        },
        "connections": {"database": db, "notify": notify},
        "otp_stats": {"total": total, "by_status": by_status},
        "metrics": {
            "avg_verification_ms": avg_verification_ms,
            "failure_breakdown": failure_breakdown,
            "top_failed_external_ids": top_failed,
            "rate_limit_active_external_ids": rl_active,
        },
        "recent_logs": [
            {
                "id": r.id,
                "external_id": str(r.external_id),
                "status": r.status,
                "attempts": r.attempts,
                "failure_reason": r.failure_reason,
                "message_id": r.message_id,
                "error_detail": r.error_detail,
                "verified_at": r.verified_at.isoformat() if r.verified_at else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in recent.all()
        ],
        "queried_at": datetime.now(UTC).isoformat(),
    }
