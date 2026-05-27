"""Operações de banco do agregado Enrollment: busca e criação idempotente.

A transição de status (`advance`) entra com os milestones de coleta (2–5).
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Enrollment, EnrollmentStatus


async def get(session: AsyncSession, external_id: UUID | str) -> Enrollment | None:
    return await session.scalar(select(Enrollment).where(Enrollment.external_id == external_id))


async def get_or_create(
    session: AsyncSession,
    external_id: UUID,
    promoter_external_id: UUID | None = None,
) -> tuple[Enrollment, bool]:
    """Retorna (enrollment, created). Idempotente por external_id.

    Usa `flush` (não `commit`): o caller controla a transação para gravar o
    evento auditivo e o agregado atomicamente.
    """
    enrollment = await get(session, external_id)
    if enrollment is not None:
        return enrollment, False
    enrollment = Enrollment(
        external_id=external_id,
        status=EnrollmentStatus.STARTED.value,
        promoter_external_id=promoter_external_id,
    )
    session.add(enrollment)
    await session.flush()
    return enrollment, True
