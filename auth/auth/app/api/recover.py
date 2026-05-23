"""Endpoint de recuperacao — usuario perdeu external_id, recupera via cpf ou phone.

Diferente de /check, este endpoint tem semantica explicita de recovery:
- Aceita apenas cpf ou phone (nunca external_id — voce esta recuperando ele)
- Resposta otimizada para o caso de uso (`otp_sent` explicito quando dispatch ocorre)
- OTP eh sempre disparado no canal conhecido (phone via notify), independente
  do campo usado para localizar o usuario.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel

from app.api.check import dispatch_otp, lookup_cpf, lookup_phone, try_acquire_otp_slot
from app.exceptions import ValidationError
from app.utils.validation import validate_cpf, validate_phone

router = APIRouter(prefix="/recover", tags=["recover"])


class RecoverRequest(BaseModel):
    cpf: str | None = None
    phone: str | None = None


@router.post(
    "",
    summary="Recupera external_id por cpf ou phone e dispara OTP no canal conhecido",
)
async def recover(data: RecoverRequest, bg: BackgroundTasks, request: Request) -> dict:
    if not data.cpf and not data.phone:
        raise ValidationError("Informe cpf ou phone.", code="MISSING_FIELD")

    redis = getattr(request.app.state, "redis", None)

    if data.cpf:
        try:
            validate_cpf(data.cpf)
        except ValueError as exc:
            raise ValidationError(str(exc), code="CPF_INVALID")
        result = await lookup_cpf(data.cpf)
    else:
        assert data.phone is not None
        try:
            validate_phone(data.phone)
        except ValueError as exc:
            raise ValidationError(str(exc), code="PHONE_INVALID")
        result = await lookup_phone(data.phone)

    if not result.get("found"):
        return {"found": False}

    external_id = result["external_id"]
    wait = await try_acquire_otp_slot(redis, external_id)
    if wait is not None:
        return {"found": True, "external_id": external_id, "otp_wait": wait}

    bg.add_task(dispatch_otp, external_id)
    return {"found": True, "external_id": external_id, "otp_sent": True}
