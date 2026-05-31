"""Notificações do funil de matrícula (CONVENTION §13).

Sempre async (via BackgroundTasks nos endpoints); falha nunca quebra fluxo.
"""

import httpx

from app.config import get_settings
from app.integrations.notify import NotifyClient
from app.models import EnrollmentStatus
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger("enrollment.notifications")

# Mensagem por status — guia o matriculando para a próxima etapa.
_ADVANCE_MESSAGES: dict[str, tuple[str, str]] = {
    EnrollmentStatus.PROFILE.value: (
        "Perfil salvo",
        "Ótimo! Agora preencha seu endereço para continuar a matrícula.",
    ),
    EnrollmentStatus.ADDRESS.value: (
        "Endereço salvo",
        "Envie seu RG (frente e verso) para continuar.",
    ),
    EnrollmentStatus.DOCUMENTS.value: (
        "RG recebido",
        "Informe seu último ano de estudo, quando foi e em que escola.",
    ),
    EnrollmentStatus.EDUCATION.value: (
        "Dados educacionais salvos",
        "Última etapa: envie uma selfie para concluir o envio.",
    ),
    EnrollmentStatus.AWAITING_RELEASE.value: (
        "Cadastro completo",
        "Recebemos todos os seus dados. Sua matrícula está aguardando "
        "a liberação do coordenador do polo.",
    ),
    EnrollmentStatus.COMPLETED.value: (
        "Matrícula liberada",
        "Parabéns! Sua matrícula foi liberada e você já é aluno.",
    ),
}


def _notify_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.notify_base_url, timeout=settings.http_timeout)


async def notify_status_advanced(external_id: str, status: str) -> None:
    """Avisa o matriculando sobre o avanço do funil."""
    msg = _ADVANCE_MESSAGES.get(status)
    if not msg:
        return
    title, content = msg
    async with _notify_client() as http:
        try:
            await NotifyClient(http).send_message(external_id=external_id, content=content, title=title)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "notify_advance_failed",
                external_id=external_id,
                status=status,
                error=str(exc),
            )


async def notify_coordinator_awaiting(
    external_id: str,
    hub_external_id: str | None,
    promoter_external_id: str | None,
) -> None:
    """Avisa o coordenador do hub que o matriculando completou o envio de dados.

    O coordenador deve ser resolvido a partir do hub do promotor. Enquanto o
    serviço `hub` não existir, enviamos a notificação ao próprio hub (se
    conhecido) e logamos a pendência para reconciliação futura.
    """
    if not hub_external_id:
        logger.info(
            "enrollment_awaiting_release_no_hub",
            external_id=external_id,
            promoter_external_id=promoter_external_id,
        )
        return
    async with _notify_client() as http:
        try:
            await NotifyClient(http).send_message(
                external_id=hub_external_id,
                content=(
                    f"Matriculando {external_id} completou o envio de dados. "
                    f"Acesse o painel para liberar a matrícula."
                ),
                title="Matrícula aguardando liberação",
                flags={
                    "enrollment_external_id": external_id,
                    "promoter_external_id": promoter_external_id,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "notify_coordinator_awaiting_failed",
                external_id=external_id,
                hub_external_id=hub_external_id,
                error=str(exc),
            )
