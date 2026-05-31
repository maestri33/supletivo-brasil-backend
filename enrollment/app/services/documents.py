"""Etapa documents — RG obrigatório (orquestra `documents`).

TODO: "sim obrigatório RG" — exige numero + foto_frente + foto_verso para
avançar address → documents.
"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import NotFound, ValidationError
from app.integrations.documents import DocumentsClient
from app.models import EnrollmentStatus
from app.schemas.documents import RgDataRequest
from app.services import enrollment as enrollment_svc

settings = get_settings()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.documents_base_url, timeout=settings.http_timeout)


def _summary(doc: dict) -> dict:
    rg = doc.get("rg") or {}
    return {
        "rg_numero": rg.get("numero"),
        "rg_orgao_emissor": rg.get("orgao_emissor"),
        "rg_data_emissao": rg.get("data_emissao"),
        "rg_foto_frente": bool(rg.get("foto_frente")),
        "rg_foto_verso": bool(rg.get("foto_verso")),
    }


async def get_documents(external_id: str) -> dict:
    async with _client() as http:
        doc = await DocumentsClient(http).get(external_id)
    return _summary(doc)


async def save_rg_data(external_id: str, payload: RgDataRequest) -> dict:
    """Atualiza campos textuais do RG no serviço `documents`."""
    fields = {
        "numero": payload.numero,
        "orgao_emissor": payload.orgao_emissor,
        "data_emissao": payload.data_emissao.isoformat() if payload.data_emissao else None,
    }
    body = {"rg": {k: v for k, v in fields.items() if v is not None}}

    async with _client() as http:
        doc = await DocumentsClient(http).update(external_id, body)
    return _summary(doc)


async def upload_rg_image(
    external_id: str, slot: str, content: bytes, filename: str, mime_type: str
) -> dict:
    async with _client() as http:
        doc = await DocumentsClient(http).upload_image(
            external_id, slot, content, filename, mime_type
        )
    return _summary(doc)


async def submit_documents(session: AsyncSession, external_id: str) -> str:
    """Valida que RG está completo (numero + frente + verso) e avança."""
    async with _client() as http:
        doc = await DocumentsClient(http).get(external_id)
    s = _summary(doc)

    if not (s["rg_numero"] and s["rg_foto_frente"] and s["rg_foto_verso"]):
        raise ValidationError(
            "Envie número, frente e verso do RG antes de continuar (RG é obrigatório)"
        )

    enrollment = await enrollment_svc.get(session, external_id)
    if not enrollment:
        raise NotFound("Matrícula não encontrada")
    enrollment_svc.advance(enrollment, EnrollmentStatus.ADDRESS, EnrollmentStatus.DOCUMENTS)
    return enrollment.status
