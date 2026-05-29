"""Correcao assincrona de submissoes via servico `ai` (BackgroundTask).

Fluxo (`run_grading`):
1. Reabre uma session propria — BackgroundTasks do FastAPI roda APOS a resposta
   HTTP, entao a session original ja' foi fechada.
2. Carrega a submissao + a materia (gabarito).
3. Chama `ai.grade()` (httpx, retry, timeout maior). Falha → mantem em PENDING,
   loga e sai (CONVENTION §14: nao bloqueia o fluxo).
4. Aplica nota: `>= grade_pass_threshold` → APPROVED; senao REJECTED.
5. Se APPROVED, checa se trainee aprovou TODAS as materias existentes:
   - sim → marca trainee como AWAITING_INTERVIEW + notifica coordenador
     (notify e' best-effort, falha vira log).

Nao promove papel aqui — promocao a `promoter` so' apos aprovacao do
coordenador, feita em `services/coordinator.py`.
"""

from uuid import UUID

from sqlalchemy import func, select

from app.config import get_settings
from app.db import async_session_maker
from app.exceptions import IntegrationError
from app.integrations.ai import AIClient, ai_http_client
from app.integrations.notify import NotifyClient, notify_http_client
from app.models import Material, Submission, SubmissionStatus, TraineeStatus
from app.services import submission as submission_svc
from app.services import trainee as trainee_svc
from app.utils.logging import get_logger

logger = get_logger("training.grading")


async def run_grading(submission_id: str) -> None:
    """Tarefa em background: corrige UMA submissao. Engole excecoes p/ nao matar
    o pool de background tasks — toda falha vira log estruturado."""
    settings = get_settings()
    log = logger.bind(submission_id=submission_id)

    try:
        async with async_session_maker() as session:
            sub = await session.scalar(
                select(Submission).where(Submission.id == str(submission_id))
            )
            if sub is None:
                log.warning("grading_submission_missing")
                return
            if sub.status != SubmissionStatus.PENDING.value:
                log.info("grading_skip_not_pending", status=sub.status)
                return

            material = await session.scalar(
                select(Material).where(Material.id == str(sub.material_id))
            )
            if material is None:
                log.warning("grading_material_missing", material_id=sub.material_id)
                return

            try:
                async with ai_http_client() as http:
                    result = await AIClient(http).grade(
                        question=material.question,
                        expected_answer=material.expected_answer,
                        student_answer=sub.answer,
                    )
            except (IntegrationError, Exception) as exc:  # noqa: BLE001 - degrade gracioso
                log.warning("grading_ai_failed", error=str(exc), error_type=type(exc).__name__)
                return

            submission_svc.apply_grading(
                sub, result.grade, result.justification, settings.grade_pass_threshold
            )
            log.info(
                "grading_applied",
                grade=result.grade,
                status=sub.status,
                material_id=sub.material_id,
            )

            if sub.status == SubmissionStatus.APPROVED.value:
                await _maybe_complete_trainee(session, UUID(sub.external_id), log)

            await session.commit()

    except Exception:  # noqa: BLE001 - background task NUNCA pode propagar
        log.exception("grading_unhandled_error")


async def _maybe_complete_trainee(session, external_id: UUID, log) -> None:
    """Se trainee aprovou TODAS as materias existentes, marca AWAITING_INTERVIEW
    e dispara notify ao coordenador (best-effort)."""
    total_materials = int(await session.scalar(select(func.count(Material.id))) or 0)
    approved = await submission_svc.approved_material_ids(session, external_id)

    if total_materials == 0 or len(approved) < total_materials:
        log.info(
            "trainee_progress",
            approved=len(approved),
            total=total_materials,
        )
        return

    trainee = await trainee_svc.get_or_create(session, external_id)
    if trainee.status == TraineeStatus.AWAITING_INTERVIEW.value:
        return
    if trainee.status != TraineeStatus.TRAINING.value:
        log.info("trainee_already_decided", status=trainee.status)
        return

    trainee_svc.mark_awaiting_interview(trainee)
    log.info("trainee_awaiting_interview", external_id=str(external_id))

    await _notify_coordinator_awaiting(external_id, log)


async def _notify_coordinator_awaiting(trainee_external_id: UUID, log) -> None:
    """Notify ao coordenador — falha NUNCA quebra o fluxo (CONVENTION §13).

    Sem cadastro de coordenadores por hub aqui (training nao conhece a relacao
    coord<->hub), entao usamos o proprio external_id do trainee como destinatario
    e a flag `audience=coordinator` para o `notify` rotear. Quando o `notify`
    evoluir para fila por papel/hub, basta ajustar este client.
    """
    try:
        async with notify_http_client() as http:
            await NotifyClient(http).send_message(
                external_id=str(trainee_external_id),
                content=(
                    "O trainee concluiu todas as materias do treinamento e esta "
                    "aguardando aprovacao da entrevista pelo coordenador."
                ),
                title="Trainee aguardando entrevista",
                flags={"audience": "coordinator", "kind": "trainee.awaiting_interview"},
            )
    except Exception as exc:  # noqa: BLE001 - best-effort
        log.warning("notify_failed", error=str(exc), error_type=type(exc).__name__)
