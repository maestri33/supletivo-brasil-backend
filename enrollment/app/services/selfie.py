"""Etapa selfie — assinatura digital + transição para awaiting_release.

Fluxo (espelha `candidate/services/selfie.py`):
  1. armazena selfie no `documents` (slot `foto`);
  2. valida heuristicamente via `ai/vision` que há uma pessoa real
     (best-effort: se `ai` cair, segue o fluxo, CONVENTION §13);
  3. avança education → selfie → awaiting_release num único POST
     (o matriculando terminou de enviar tudo; falta só o coordenador liberar).
"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import IntegrationError, NotFound, ValidationError
from app.integrations.ai import AIClient
from app.integrations.documents import DocumentsClient
from app.models import EnrollmentStatus
from app.services import enrollment as enrollment_svc
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger("enrollment.selfie")

SELFIE_SLOT = "foto"

# Termos pt-br que indicam presença de pessoa na descrição do ai/vision.
_PERSON_TERMS = (
    "pessoa",
    "homem",
    "mulher",
    "menino",
    "menina",
    "rosto",
    "face",
    "selfie",
    "humano",
    "cabelo",
    "olhos",
    "sorri",
    "retrato",
)


async def get_selfie(external_id: str) -> dict:
    async with httpx.AsyncClient(
        base_url=settings.documents_base_url, timeout=settings.http_timeout
    ) as http:
        doc = await DocumentsClient(http).get(external_id)
    return {"has_selfie": bool(doc.get(SELFIE_SLOT))}


async def _verify_selfie(external_id: str) -> tuple[bool, str | None]:
    """Roda ai/vision na selfie. Retorna (verified, description).

    Falha do `ai` NÃO bloqueia (verified=False, segue o funil). Imagem que
    claramente não tem pessoa levanta ValidationError.
    """
    image_url = (
        f"{settings.documents_base_url}/api/v1/documents/{external_id}/images/{SELFIE_SLOT}"
    )
    try:
        async with httpx.AsyncClient(
            base_url=settings.ai_base_url, timeout=settings.http_timeout
        ) as http:
            description = await AIClient(http).vision(image_url)
    except (IntegrationError, httpx.HTTPError) as exc:
        logger.warning("selfie_vision_unavailable", external_id=external_id, error=str(exc))
        return False, None

    lowered = (description or "").lower()
    if description and not any(term in lowered for term in _PERSON_TERMS):
        raise ValidationError("A selfie não parece conter uma pessoa real. Envie outra foto.")
    return True, description


async def submit_selfie(
    session: AsyncSession,
    external_id: str,
    content: bytes,
    filename: str,
    mime_type: str,
) -> dict:
    """Armazena selfie, valida e avança para awaiting_release (envio terminou).

    A liberação final fica com o coordenador (endpoint /release), que promove
    a role para `student` no `roles`.
    """
    async with httpx.AsyncClient(
        base_url=settings.documents_base_url, timeout=settings.http_timeout
    ) as http:
        await DocumentsClient(http).upload_image(
            external_id, SELFIE_SLOT, content, filename, mime_type
        )

    verified, description = await _verify_selfie(external_id)

    enrollment = await enrollment_svc.get(session, external_id)
    if not enrollment:
        raise NotFound("Matrícula não encontrada")
    # Transição composta: education → selfie → awaiting_release (PRD §5.9).
    enrollment_svc.advance(enrollment, EnrollmentStatus.EDUCATION, EnrollmentStatus.SELFIE)
    enrollment_svc.advance(
        enrollment, EnrollmentStatus.SELFIE, EnrollmentStatus.AWAITING_RELEASE
    )
    return {
        "status": enrollment.status,
        "verified": verified,
        "description": description,
    }
