"""Estado do Trainee — get-or-create, transicoes de status com guard.

Maquina de estados:
- training            → awaiting_interview  (todas as materias aprovadas)
- awaiting_interview  → approved            (coordenador aprovou + promote em roles)
- awaiting_interview  → rejected            (coordenador rejeitou + motivo)

Toda transicao e' chamada por services/grading.py (auto) ou
api/authenticated/coordinator.py (manual). Quem chama controla commit.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import Conflict, NotFound
from app.models import Trainee, TraineeStatus


async def get_by_external_id(session: AsyncSession, external_id: UUID) -> Trainee | None:
    return await session.scalar(select(Trainee).where(Trainee.external_id == str(external_id)))


async def get_or_create(session: AsyncSession, external_id: UUID) -> Trainee:
    """Idempotente — chamado na primeira submissao de cada trainee."""
    existing = await get_by_external_id(session, external_id)
    if existing is not None:
        return existing
    trainee = Trainee(
        external_id=str(external_id),
        status=TraineeStatus.TRAINING.value,
    )
    session.add(trainee)
    await session.flush()
    return trainee


async def get_or_404(session: AsyncSession, external_id: UUID) -> Trainee:
    trainee = await get_by_external_id(session, external_id)
    if trainee is None:
        raise NotFound("Trainee nao encontrado")
    return trainee


def mark_awaiting_interview(trainee: Trainee) -> bool:
    """Transita TRAINING -> AWAITING_INTERVIEW. No-op se ja' esta nesse estado.

    Retorna True se a transicao ocorreu agora, False se ja' estava (idempotente).
    Levanta Conflict se o trainee ja' foi aprovado/rejeitado (estado terminal).
    """
    if trainee.status == TraineeStatus.AWAITING_INTERVIEW.value:
        return False
    if trainee.status != TraineeStatus.TRAINING.value:
        raise Conflict(
            f"Trainee em estado terminal '{trainee.status}', nao pode voltar p/ entrevista"
        )
    trainee.status = TraineeStatus.AWAITING_INTERVIEW.value
    trainee.awaiting_interview_at = datetime.now(UTC)
    return True


def approve_by_coordinator(trainee: Trainee, coordinator_external_id: UUID) -> None:
    """AWAITING_INTERVIEW -> APPROVED. Caller deve promover papel no roles a seguir."""
    if trainee.status != TraineeStatus.AWAITING_INTERVIEW.value:
        raise Conflict(
            f"Trainee em '{trainee.status}' — so' pode aprovar quando 'awaiting_interview'"
        )
    trainee.status = TraineeStatus.APPROVED.value
    trainee.coordinator_external_id = str(coordinator_external_id)
    trainee.coordinator_decision_at = datetime.now(UTC)
    trainee.rejection_reason = None


def reject_by_coordinator(trainee: Trainee, coordinator_external_id: UUID, reason: str) -> None:
    """AWAITING_INTERVIEW -> REJECTED. Motivo obrigatorio (TODO/PRD §8.6)."""
    if trainee.status != TraineeStatus.AWAITING_INTERVIEW.value:
        raise Conflict(
            f"Trainee em '{trainee.status}' — so' pode rejeitar quando 'awaiting_interview'"
        )
    trainee.status = TraineeStatus.REJECTED.value
    trainee.coordinator_external_id = str(coordinator_external_id)
    trainee.coordinator_decision_at = datetime.now(UTC)
    trainee.rejection_reason = reason
