"""Enrollment fee schemas."""

from datetime import date, datetime
from decimal import Decimal

from app.schemas import APIModel


class EnrollmentFeeCreate(APIModel):
    """Schema para criar uma taxa de matrícula."""

    coordinator_id: str
    student_external_id: str
    description: str
    amount: Decimal
    due_date: date | None = None


class EnrollmentFeePayRequest(APIModel):
    """Schema para marcar uma taxa como paga."""

    payment_external_id: str | None = None


class EnrollmentFeeResponse(APIModel):
    """Schema de resposta com dados completos da taxa."""

    id: str
    coordinator_id: str
    student_external_id: str
    description: str
    amount: Decimal
    due_date: date | None = None
    status: str
    payment_external_id: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class EnrollmentFeeListResponse(APIModel):
    """Schema para listagem paginada de taxas."""

    items: list[EnrollmentFeeResponse]
    total: int
