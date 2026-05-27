"""Notificacoes do funil (§11) — sempre assincronas e tolerantes a falha.

Sao agendadas via BackgroundTasks nos endpoints; nunca quebram o fluxo principal
se o notify estiver fora (apenas logam).
"""

import httpx

from app.config import get_settings
from app.integrations.notify import NotifyClient
from app.models import CandidateStatus
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger("candidate.notifications")

# Mensagem que motiva o candidato a seguir para a proxima etapa do funil.
_ADVANCE_MESSAGES: dict[str, tuple[str, str]] = {
    CandidateStatus.PERSONAL.value: (
        "Dados iniciais salvos",
        "Otimo! Agora preencha seus dados pessoais para continuar seu cadastro.",
    ),
    CandidateStatus.EDUCATION.value: (
        "Dados pessoais salvos",
        "Falta pouco! Informe seus dados educacionais.",
    ),
    CandidateStatus.BIRTH.value: (
        "Dados educacionais salvos",
        "Agora preencha seus dados de nascimento.",
    ),
    CandidateStatus.ADDRESS.value: (
        "Quase la",
        "Informe seu endereco para avancar no cadastro.",
    ),
    CandidateStatus.DOCUMENTS.value: (
        "Endereco salvo",
        "Envie seu RG ou CNH (dados e fotos) para continuar.",
    ),
    CandidateStatus.PIXKEY.value: (
        "Documentos recebidos",
        "Cadastre sua chave PIX — e' por onde voce vai receber suas comissoes.",
    ),
    CandidateStatus.SELFIE.value: (
        "Chave PIX validada",
        "Ultima etapa: envie uma selfie real para concluir seu cadastro.",
    ),
    CandidateStatus.COMPLETED.value: (
        "Cadastro concluido!",
        "Parabens! Seu cadastro foi concluido e voce avancou para o treinamento.",
    ),
}


async def notify_captured(external_id: str, phone: str, hub_external_id: str) -> None:
    """Boas-vindas ao novo lead + aviso ao hub (etapa de captura)."""
    async with httpx.AsyncClient(
        base_url=settings.notify_base_url, timeout=settings.http_timeout
    ) as client:
        notify = NotifyClient(client)
        try:
            await notify.send_message(
                external_id=external_id,
                content=(
                    "Seu cadastro foi iniciado com sucesso! "
                    "Continue preenchendo suas informacoes para avancar."
                ),
                title="Cadastro iniciado",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("notify_captured_lead_failed", external_id=external_id, error=str(exc))
        try:
            await notify.send_message(
                external_id=hub_external_id,
                content=f"Novo candidato cadastrado. Telefone: {phone}",
                title="Novo candidato",
                flags={"candidate_external_id": external_id},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("notify_captured_hub_failed", external_id=external_id, error=str(exc))


async def notify_status_advanced(external_id: str, status: str) -> None:
    """Avisa o candidato sobre o avanco e o que vem a seguir."""
    msg = _ADVANCE_MESSAGES.get(status)
    if not msg:
        return
    title, content = msg
    async with httpx.AsyncClient(
        base_url=settings.notify_base_url, timeout=settings.http_timeout
    ) as client:
        notify = NotifyClient(client)
        try:
            await notify.send_message(external_id=external_id, content=content, title=title)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "notify_advance_failed", external_id=external_id, status=status, error=str(exc)
            )


async def notify_hub_completed(external_id: str, hub_external_id: str | None) -> None:
    """Avisa o hub que um candidato concluiu e virou aspirante a treinamento."""
    if not hub_external_id:
        return
    async with httpx.AsyncClient(
        base_url=settings.notify_base_url, timeout=settings.http_timeout
    ) as client:
        notify = NotifyClient(client)
        try:
            await notify.send_message(
                external_id=hub_external_id,
                content="Um candidato concluiu o cadastro e avancou para o treinamento.",
                title="Candidato concluido",
                flags={"candidate_external_id": external_id},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("notify_completed_hub_failed", external_id=external_id, error=str(exc))
