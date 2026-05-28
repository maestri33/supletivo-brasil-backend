"""Etapa release — liberação manual pelo coordenador → conclusão da matrícula.

Promove a role do matriculando enrollment → student via `roles` e marca o
agregado como `completed`. Os "dados da plataforma" (platform_id, classe)
ficam no payload do evento auditivo `enrollment.completed` em
`enrollment_events` (não cria tabela própria para isso — minimalismo §20).
"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import NotFound
from app.integrations.roles import RolesClient
from app.models import EnrollmentEvent, EnrollmentStatus
from app.schemas.release import ReleasePostRequest
from app.services import enrollment as enrollment_svc
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger("enrollment.release")

RELEASE_EVENT = "enrollment.completed"


async def release(
    session: AsyncSession,
    external_id: str,
    payload: ReleasePostRequest,
    coordinator_external_id: str,
) -> str:
    """Promove a role para student + avança awaiting_release → completed.

    A promoção da role é BLOQUEANTE (CONVENTION §7 nota: ações intencionalmente
    bloqueantes na promoção de papel são permitidas). Falha → o endpoint
    retorna 502 e o coordenador retenta.
    """
    enrollment = await enrollment_svc.get(session, external_id)
    if not enrollment:
        raise NotFound("Matrícula não encontrada")

    # Promove enrollment → student (idempotente no client).
    async with httpx.AsyncClient(
        base_url=settings.roles_base_url, timeout=settings.http_timeout
    ) as http:
        await RolesClient(http).promote(external_id, "student")

    # Audita a liberação no log de eventos — guarda os dados da plataforma
    # informados pelo coordenador (platform_id, classe, notas).
    audit_payload = payload.model_dump()
    audit_payload["coordinator_external_id"] = coordinator_external_id
    session.add(
        EnrollmentEvent(
            external_id=enrollment.external_id,
            event=RELEASE_EVENT,
            promoter_external_id=enrollment.promoter_external_id,
            payload=audit_payload,
        )
    )

    enrollment_svc.advance(
        enrollment, EnrollmentStatus.AWAITING_RELEASE, EnrollmentStatus.COMPLETED
    )
    logger.info(
        "enrollment_released",
        external_id=external_id,
        coordinator=coordinator_external_id,
        platform_id=payload.platform_id,
    )
    return enrollment.status
