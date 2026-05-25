"""Etapa de documentos (RG ou CNH) — orquestra o servico `documents`.

O documents e' o dono do armazenamento; aqui enviamos dados/fotos, lemos o
estado e validamos a completude antes de avancar.
"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import NotFound, ValidationError
from app.integrations.documents import DocumentsClient
from app.models import CandidateStatus
from app.schemas.documents import DocumentDataRequest
from app.services import candidate as candidate_svc

settings = get_settings()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.documents_base_url, timeout=settings.http_timeout)


def _summary(doc: dict) -> dict:
    rg = doc.get("rg") or {}
    cnh = doc.get("cnh") or {}
    return {
        "rg_numero": rg.get("numero"),
        "rg_foto_frente": bool(rg.get("foto_frente")),
        "rg_foto_verso": bool(rg.get("foto_verso")),
        "cnh_numero": cnh.get("numero"),
        "cnh_foto_frente": bool(cnh.get("foto_frente")),
        "cnh_foto_verso": bool(cnh.get("foto_verso")),
    }


async def get_documents(external_id: str) -> dict:
    async with _client() as http:
        doc = await DocumentsClient(http).get(external_id)
    return _summary(doc)


async def save_data(external_id: str, payload: DocumentDataRequest) -> dict:
    """Atualiza os campos textuais do RG ou CNH no documents-service."""
    if payload.doc_type == "rg":
        fields = {
            "numero": payload.numero,
            "orgao_emissor": payload.orgao_emissor,
            "data_emissao": payload.data_emissao.isoformat() if payload.data_emissao else None,
        }
        body = {"rg": {k: v for k, v in fields.items() if v is not None}}
    else:  # cnh
        fields = {
            "numero": payload.numero,
            "categoria": payload.categoria,
            "data_nascimento": (
                payload.data_nascimento.isoformat() if payload.data_nascimento else None
            ),
            "validade": payload.validade.isoformat() if payload.validade else None,
            "registro_nacional": payload.registro_nacional,
        }
        body = {"cnh": {k: v for k, v in fields.items() if v is not None}}

    async with _client() as http:
        doc = await DocumentsClient(http).update(external_id, body)
    return _summary(doc)


async def upload_image(
    external_id: str, slot: str, content: bytes, filename: str, mime_type: str
) -> dict:
    async with _client() as http:
        doc = await DocumentsClient(http).upload_image(
            external_id, slot, content, filename, mime_type
        )
    return _summary(doc)


async def submit(session: AsyncSession, external_id: str) -> str:
    """Valida que RG OU CNH esta' completo (numero + frente + verso) e avanca."""
    async with _client() as http:
        doc = await DocumentsClient(http).get(external_id)
    s = _summary(doc)

    rg_ok = bool(s["rg_numero"] and s["rg_foto_frente"] and s["rg_foto_verso"])
    cnh_ok = bool(s["cnh_numero"] and s["cnh_foto_frente"] and s["cnh_foto_verso"])
    if not (rg_ok or cnh_ok):
        raise ValidationError("Envie numero, frente e verso de pelo menos um documento (RG ou CNH)")

    candidate = await candidate_svc.get(session, external_id)
    if not candidate:
        raise NotFound("Candidato nao encontrado")
    candidate_svc.advance(candidate, CandidateStatus.DOCUMENTS, CandidateStatus.PIXKEY)
    return candidate.status
