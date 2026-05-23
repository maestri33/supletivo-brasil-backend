"""Pydantic schemas for OTP."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OTPCreate(BaseModel):
    external_id: UUID


class OTPCheck(BaseModel):
    external_id: UUID
    code: str = Field(min_length=1, max_length=10)


class OTPCheckResponse(BaseModel):
    valid: bool
    detail: str = "ok"


class OTPRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: UUID
    status: str
    attempts: int = 0
    failure_reason: str | None = None
    message_id: int | None = None
    error_detail: str | None = None
    verified_at: datetime | None = None
    created_at: datetime
