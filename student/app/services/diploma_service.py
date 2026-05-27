"""Diploma — emissao pelo coordenador + retirada com foto pelo aluno.

Na virada para VETERAN dispara, em background:
  1. comissao do coordenador via app `commissions` (idempotente);
  2. atribuicao da role `veterano` via app `roles` (multi-role — mantem student).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session_maker
from app.exceptions import (
    DiplomaAlreadyIssued,
    DiplomaAlreadyPickedUp,
    DiplomaNotFound,
)
from app.integrations.commissions import CommissionsClient
from app.integrations.roles import RolesClient
from app.models import Student, StudentDiploma, StudentStatus
from app.services import student_service
from app.utils.logging import get_logger

logger = get_logger("student.diploma")
settings = get_settings()


async def issue_diploma(
    session: AsyncSession,
    *,
    student: Student,
    coordinator_external_id: UUID,
) -> StudentDiploma:
    """Coord emite (certificado + historico). AWAITING_DIPLOMA_ISSUANCE -> AWAITING_PICKUP.

    Atalho de fluxo: se o aluno passou da prova mas ainda esta em
    AWAITING_DOCUMENTATION_DISPATCH (pre-dispatch resolvido fora deste app),
    aceitamos como origem tambem — caso contrario o coord nao consegue avancar.
    """
    student_service.advance(
        student,
        allowed_from=(
            StudentStatus.AWAITING_DOCUMENTATION_DISPATCH,
            StudentStatus.AWAITING_DIPLOMA_ISSUANCE,
        ),
        to=StudentStatus.AWAITING_PICKUP,
    )
    existing = await session.scalar(
        select(StudentDiploma).where(StudentDiploma.student_id == student.id)
    )
    if existing is not None and existing.issued_at is not None:
        raise DiplomaAlreadyIssued("Diploma ja foi emitido para este aluno")

    diploma = existing or StudentDiploma(student_id=student.id)
    diploma.issued_by_external_id = coordinator_external_id
    diploma.issued_at = datetime.now(UTC)
    if existing is None:
        session.add(diploma)
    await session.flush()
    await session.refresh(diploma)
    return diploma


async def pickup_diploma(
    session: AsyncSession,
    *,
    student: Student,
    pickup_photo_external_id: UUID,
) -> StudentDiploma:
    """Aluno registra retirada. AWAITING_PICKUP -> VETERAN. Side-effects assincronos."""
    student_service.advance(
        student,
        allowed_from=(StudentStatus.AWAITING_PICKUP,),
        to=StudentStatus.VETERAN,
    )

    diploma = await session.scalar(
        select(StudentDiploma).where(StudentDiploma.student_id == student.id)
    )
    if diploma is None:
        raise DiplomaNotFound("Diploma nao emitido para este aluno")
    if diploma.picked_up_at is not None:
        raise DiplomaAlreadyPickedUp("Diploma ja foi retirado")

    diploma.picked_up_at = datetime.now(UTC)
    diploma.pickup_photo_external_id = pickup_photo_external_id
    await session.flush()
    await session.refresh(diploma)
    return diploma


async def trigger_graduation_side_effects(
    student_id: UUID,
    student_external_id: UUID,
    coordinator_external_id: UUID,
) -> None:
    """Background — dispara comissao e atribui role `veterano`.

    Idempotente: marca commission_triggered_at apos sucesso. Reentrada nao redispara.
    """
    async with async_session_maker() as session:
        diploma = await session.scalar(
            select(StudentDiploma).where(StudentDiploma.student_id == student_id)
        )
        if diploma is None:
            logger.warning("graduation.diploma_missing", student_id=str(student_id))
            return

        if diploma.commission_triggered_at is None:
            try:
                async with httpx.AsyncClient(
                    base_url=settings.commissions_base_url,
                    timeout=settings.http_timeout,
                ) as client:
                    await CommissionsClient(client).trigger_graduation(
                        coordinator_external_id=str(coordinator_external_id),
                        source_external_id=str(student_id),
                        amount_cents=settings.coordinator_commission_cents,
                    )
                diploma.commission_triggered_at = datetime.now(UTC)
                await session.commit()
                logger.info(
                    "graduation.commission_triggered",
                    student_id=str(student_id),
                    coordinator=str(coordinator_external_id),
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "graduation.commission_failed",
                    student_id=str(student_id),
                    error=str(exc),
                )

    # Role veterano — separado, mesmo se a comissao falhar.
    try:
        async with httpx.AsyncClient(
            base_url=settings.roles_base_url, timeout=settings.http_timeout
        ) as client:
            await RolesClient(client).promote(str(student_external_id), "veterano")
        logger.info("graduation.role_assigned", external_id=str(student_external_id))
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "graduation.role_failed",
            external_id=str(student_external_id),
            error=str(exc),
        )


async def get_diploma(
    session: AsyncSession, *, student: Student
) -> StudentDiploma | None:
    return await session.scalar(
        select(StudentDiploma).where(StudentDiploma.student_id == student.id)
    )
