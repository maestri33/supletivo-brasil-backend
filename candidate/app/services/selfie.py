"""Etapa final — selfie real ("assinatura de contrato") + conclusao do funil.

Fluxo:
  1. armazena a selfie no `documents` (slot `foto`);
  2. valida heuristicamente via `ai` /image/vision que ha' uma pessoa real
     (nao e' liveness/biometria — apenas barra imagem obviamente invalida;
     se o `ai` estiver fora, nao bloqueia o funil, §13);
  3. promove o papel lead -> training no `roles`;
  4. encerra o candidate em `completed`.

Pendencia de integracao (documentada, sem TODO orfao): a criacao do registro no
servico `training` sera' feita quando esse servico existir (Parte B do plano).
Hoje a promocao de papel ja' marca o usuario como `training` no `roles`.
"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import IntegrationError, NotFound, ValidationError
from app.integrations.ai import AIClient
from app.integrations.documents import DocumentsClient
from app.integrations.roles import RolesClient
from app.models import CandidateStatus
from app.services import candidate as candidate_svc
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger("candidate.selfie")

SELFIE_SLOT = "foto"

# Termos (pt-br) que indicam presenca de uma pessoa na descricao do ai/vision.
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

    Falha do ai NAO bloqueia (verified=False, segue o funil). Imagem que
    claramente nao tem pessoa levanta ValidationError.
    """
    image_url = f"{settings.documents_base_url}/api/v1/documents/{external_id}/images/{SELFIE_SLOT}"
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
        raise ValidationError("A selfie nao parece conter uma pessoa real. Envie outra foto.")
    return True, description


async def submit_selfie(
    session: AsyncSession,
    external_id: str,
    content: bytes,
    filename: str,
    mime_type: str,
) -> dict:
    """Armazena, valida, promove o papel e conclui o cadastro."""
    async with httpx.AsyncClient(
        base_url=settings.documents_base_url, timeout=settings.http_timeout
    ) as http:
        await DocumentsClient(http).upload_image(
            external_id, SELFIE_SLOT, content, filename, mime_type
        )

    verified, description = await _verify_selfie(external_id)

    # Promove lead -> training (idempotente; se falhar, NAO conclui o funil).
    async with httpx.AsyncClient(
        base_url=settings.roles_base_url, timeout=settings.http_timeout
    ) as http:
        await RolesClient(http).promote(external_id, "training")

    candidate = await candidate_svc.get(session, external_id)
    if not candidate:
        raise NotFound("Candidato nao encontrado")
    candidate_svc.advance(candidate, CandidateStatus.SELFIE, CandidateStatus.COMPLETED)

    return {"status": candidate.status, "verified": verified, "description": description}
