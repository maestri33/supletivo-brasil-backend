"""Decisao do coordenador — aprova/rejeita trainee e promove papel no `roles`.

Concentra as duas acoes pos-entrevista para ficar obvio que a promocao a
`promoter` so' acontece com decisao manual do coordenador (PRD §8: aprovacao
tecnica via IA + aprovacao manual via coord).

Promote do papel e' a unica integracao **bloqueante** deste app — se o `roles`
estiver fora, NAO marcamos o trainee como APPROVED (estado e papel ficariam
desalinhados). Falha vira 502 via IntegrationError. CONVENTION §7: integracao
bloqueante e' a excecao, documentada aqui.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import IntegrationError, NotFound
from app.integrations.notify import NotifyClient, notify_http_client
from app.integrations.roles import RolesClient, roles_http_client
from app.models import Trainee, TraineeStatus
from app.services import trainee as trainee_svc
from app.utils.logging import get_logger

logger = get_logger("training.coordinator")


async def _ensure_awaiting(session: AsyncSession, trainee_external_id: UUID) -> Trainee:
    trainee = await trainee_svc.get_by_external_id(session, trainee_external_id)
    if trainee is None:
        raise NotFound("Trainee nao encontrado")
    if trainee.status != TraineeStatus.AWAITING_INTERVIEW.value:
        from app.exceptions import Conflict

        raise Conflict(
            f"Trainee em '{trainee.status}' — so' aprova/rejeita quando 'awaiting_interview'"
        )
    return trainee


async def approve_interview(
    session: AsyncSession,
    *,
    trainee_external_id: UUID,
    coordinator_external_id: UUID,
) -> Trainee:
    """Aprovacao manual → promove no roles → marca trainee APPROVED → notifica.

    Ordem importa: promovemos PRIMEIRO no roles. Se falhar, levantamos
    IntegrationError e nao gravamos status APPROVED (consistencia entre estado
    e papel). Se promote da' sucesso e o commit local falhar, o usuario fica
    como `promoter` no roles + `awaiting_interview` aqui — reconciliacao manual,
    mas o usuario nao fica preso.
    """
    settings = get_settings()
    trainee = await _ensure_awaiting(session, trainee_external_id)

    try:
        async with roles_http_client() as http:
            await RolesClient(http).promote(str(trainee_external_id), settings.role_promoted_target)
    except IntegrationError:
        logger.exception("promote_failed", external_id=str(trainee_external_id))
        raise

    trainee_svc.approve_by_coordinator(trainee, coordinator_external_id)
    await session.flush()

    logger.info(
        "trainee_promoted",
        external_id=str(trainee_external_id),
        coordinator=str(coordinator_external_id),
        to_role=settings.role_promoted_target,
    )

    await _notify_decision(
        trainee_external_id,
        title="Aprovado para promotor",
        content=(
            "Sua entrevista foi aprovada pelo coordenador. Voce agora e' promotor da plataforma."
        ),
        kind="trainee.promoted",
    )
    return trainee


async def reject_interview(
    session: AsyncSession,
    *,
    trainee_external_id: UUID,
    coordinator_external_id: UUID,
    reason: str,
) -> Trainee:
    """Rejeicao manual → marca REJECTED + motivo → notifica. NAO promove papel."""
    trainee = await _ensure_awaiting(session, trainee_external_id)

    trainee_svc.reject_by_coordinator(trainee, coordinator_external_id, reason)
    await session.flush()

    logger.info(
        "trainee_rejected",
        external_id=str(trainee_external_id),
        coordinator=str(coordinator_external_id),
    )

    await _notify_decision(
        trainee_external_id,
        title="Entrevista nao aprovada",
        content=f"Sua entrevista nao foi aprovada. Motivo: {reason}",
        kind="trainee.rejected",
    )
    return trainee


async def _notify_decision(external_id: UUID, *, title: str, content: str, kind: str) -> None:
    """Notify best-effort — falha vira log, nao quebra a decisao do coord."""
    try:
        async with notify_http_client() as http:
            await NotifyClient(http).send_message(
                external_id=str(external_id),
                content=content,
                title=title,
                flags={"kind": kind},
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "notify_failed",
            external_id=str(external_id),
            kind=kind,
            error=str(exc),
            error_type=type(exc).__name__,
        )
