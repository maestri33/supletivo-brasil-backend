"""Etapa education — persiste dados educacionais localmente e avança.

PRD §4: ao contrário das demais etapas (delegadas ao serviço dono), os dados
educacionais ficam no schema `enrollment` (tabela `educational_data`).
1:1 com o agregado via `enrollment_id` — `enrollment.refresh()` para garantir
unicidade na inserção.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFound
from app.models import EducationalData, EnrollmentStatus
from app.schemas.education import EducationPostRequest
from app.services import enrollment as enrollment_svc


async def get_education(session: AsyncSession, external_id: str) -> dict | None:
    enrollment = await enrollment_svc.get(session, external_id)
    if not enrollment:
        return None
    edu = await session.scalar(
        select(EducationalData).where(EducationalData.enrollment_id == enrollment.id)
    )
    if not edu:
        return {}
    return {
        "last_year_studied": edu.last_year_studied,
        "last_year_date": edu.last_year_date,
        "last_school": edu.last_school,
    }


async def save_education(
    session: AsyncSession,
    external_id: str,
    payload: EducationPostRequest,
) -> str:
    """Grava (ou substitui) EducationalData e avança documents → education."""
    enrollment = await enrollment_svc.get(session, external_id)
    if not enrollment:
        raise NotFound("Matrícula não encontrada")

    edu = await session.scalar(
        select(EducationalData).where(EducationalData.enrollment_id == enrollment.id)
    )
    if edu is None:
        edu = EducationalData(
            enrollment_id=enrollment.id,
            last_year_studied=payload.last_year_studied,
            last_year_date=payload.last_year_date,
            last_school=payload.last_school,
        )
        session.add(edu)
    else:
        # Substituição idempotente: dono pode reenviar antes de avançar.
        edu.last_year_studied = payload.last_year_studied
        edu.last_year_date = payload.last_year_date
        edu.last_school = payload.last_school

    enrollment_svc.advance(enrollment, EnrollmentStatus.DOCUMENTS, EnrollmentStatus.EDUCATION)
    return enrollment.status
