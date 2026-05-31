"""Health/readiness endpoints — Asaas app."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.metrics import set_hmac_configured
from app.services.webhook_security import webhook_hmac_configured

router = APIRouter()


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict:
    """Health check — DB ping + webhook security status."""
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    hmac_ok = await webhook_hmac_configured(session)
    set_hmac_configured(hmac_ok)

    return {
        "status": "ok" if db_ok else "degraded",
        "service": "asaas",
        "db": db_ok,
        "webhook_security": {
            "webhook_hmac_configured": hmac_ok,
        },
    }


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict:  # noqa: B008
    """Readiness probe — DB connectivity + webhook security gate."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        return {"status": "not_ready", "detail": str(exc)}

    hmac_ok = await webhook_hmac_configured(session)
    set_hmac_configured(hmac_ok)
    if not hmac_ok:
        return {"status": "not_ready", "detail": "webhook_hmac_not_configured"}

    return {"status": "ready", "webhook_security": {"webhook_hmac_configured": True}}
