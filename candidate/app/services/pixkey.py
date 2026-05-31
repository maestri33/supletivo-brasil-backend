"""Etapa de chave PIX — validada e cadastrada no servico `asaas` (dono do Asaas).

O documento do titular (CPF) e' lido do perfil do candidato — nao e' informado
pelo usuario — para o asaas conferir no DICT que a chave pertence a ele.
"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import NotFound, ValidationError
from app.integrations.asaas import AsaasClient
from app.integrations.profiles import ProfilesClient
from app.models import CandidateStatus
from app.services import candidate as candidate_svc

settings = get_settings()

_CPF_KEYS = ("cpf", "document", "cpf_cnpj")


async def _holder_document(external_id: str) -> str:
    """Le o CPF do candidato no perfil (profiles)."""
    async with httpx.AsyncClient(
        base_url=settings.profiles_base_url, timeout=settings.http_timeout
    ) as http:
        profile = await ProfilesClient(http).get_one(external_id)
    for key in _CPF_KEYS:
        value = profile.get(key)
        if value:
            return str(value)
    raise ValidationError("CPF do candidato nao encontrado no perfil")


async def get_pixkey(external_id: str) -> dict:
    async with httpx.AsyncClient(
        base_url=settings.asaas_base_url, timeout=settings.http_timeout
    ) as http:
        try:
            data = await AsaasClient(http).get_pixkey(external_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {}
            raise
    return {
        "key": data.get("key"),
        "key_type": data.get("key_type"),
        "holder_name": data.get("holder_name"),
        "bank_name": data.get("bank_name"),
    }


async def save_pixkey(session: AsyncSession, external_id: str, key: str, key_type: str) -> dict:
    """Valida a chave no asaas (DICT + titular) e avanca pixkey -> selfie."""
    document = await _holder_document(external_id)

    async with httpx.AsyncClient(
        base_url=settings.asaas_base_url, timeout=settings.http_timeout
    ) as http:
        result = await AsaasClient(http).create_pixkey(
            external_id=external_id,
            document=document,
            key=key,
            key_type=key_type,
        )

    candidate = await candidate_svc.get(session, external_id)
    if not candidate:
        raise NotFound("Candidato nao encontrado")
    candidate_svc.advance(candidate, CandidateStatus.PIXKEY, CandidateStatus.SELFIE)
    return {
        "status": candidate.status,
        "holder_name": result.get("holder_name"),
        "bank_name": result.get("bank_name"),
    }
