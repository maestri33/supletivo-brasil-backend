"""OTP endpoints — /api/v1/otp (SQLAlchemy 2)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import http_client_dep
from app.db import get_session
from app.schemas.otp import OTPCheck, OTPCheckResponse, OTPCreate, OTPRead
from app.services import otp as otp_service

router = APIRouter(prefix="/api/v1/otp", tags=["otp"])


@router.post(
    "",
    response_model=OTPRead,
    status_code=status.HTTP_201_CREATED,
    summary="Gerar e enviar OTP",
)
async def create_otp(
    payload: OTPCreate,
    http=Depends(http_client_dep),
    session: AsyncSession = Depends(get_session),
) -> OTPRead:
    otp_log = await otp_service.generate_and_send(
        session, http, external_id=payload.external_id,
    )
    return OTPRead.model_validate(otp_log)


@router.get("", response_model=list[OTPRead], summary="Listar OTPs")
async def list_otps(
    external_id: UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[OTPRead]:
    logs = await otp_service.list_logs(
        session, external_id=external_id, status=status_filter,
        limit=limit, offset=offset,
    )
    return [OTPRead.model_validate(log) for log in logs]


@router.post("/check", response_model=OTPCheckResponse, summary="Validar OTP")
async def verify_otp(
    payload: OTPCheck,
    http=Depends(http_client_dep),
    session: AsyncSession = Depends(get_session),
) -> OTPCheckResponse:
    result = await otp_service.verify_code(
        session, http, external_id=payload.external_id, code=payload.code,
    )
    return OTPCheckResponse(**result)


@router.get("/logs", response_model=list[OTPRead], summary="Listar logs de OTP")
async def list_otp_logs(
    external_id: UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[OTPRead]:
    logs = await otp_service.list_logs(
        session, external_id=external_id, status=status_filter,
        limit=limit, offset=offset,
    )
    return [OTPRead.model_validate(log) for log in logs]
