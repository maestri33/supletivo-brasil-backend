"""Webhook do notify — recebe callback com status de entrega (SQLAlchemy 2)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.otp import OTPLog
from app.utils.logging import get_logger

router = APIRouter(prefix="/webhook", tags=["webhook"])
log = get_logger(__name__)


@router.post("/notify/{message_id}")
async def notify_callback(
    message_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Callback do notify com o status final da mensagem."""
    data = await request.json()

    log.info("webhook.received", message_id=message_id, whatsapp_status=data.get("whatsapp_status"))

    otp_log = await session.scalar(select(OTPLog).where(OTPLog.message_id == message_id))
    if otp_log is None:
        log.warning("webhook.unknown_message", message_id=message_id)
        return {"ok": False, "detail": "mensagem desconhecida"}

    notify_status = data.get("whatsapp_status", "unknown")
    if notify_status == "sent":
        otp_log.status = "sent"
    elif notify_status in ("failed", "rejected"):
        otp_log.status = "failed"
        otp_log.failure_reason = "notify_permanent"
        otp_log.error_detail = f"Notify reportou {notify_status}"

    await session.commit()
    log.info("webhook.updated", message_id=message_id, otp_log_id=otp_log.id, new_status=otp_log.status)
    return {"ok": True}
