"""Etapa de endereco — orquestra o servico `address` (CEP primeiro, sem duplicar).

O endereco e' vinculado a entidade pelo tipo `lead` (o usuario ainda e' um lead
durante o funil), mantendo a mesma chave usada nas demais integracoes.
"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import NotFound
from app.integrations.address import AddressClient
from app.models import CandidateStatus
from app.schemas.address import AddressPostRequest
from app.services import candidate as candidate_svc

settings = get_settings()

ENTITY_TYPE = "lead"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.addresses_base_url, timeout=settings.http_timeout)


async def get_address(external_id: str) -> dict:
    async with _client() as http:
        try:
            entity = await AddressClient(http).get_entity_address(ENTITY_TYPE, external_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {}
            raise
    addr = entity.get("address") or {}
    return {
        "cep": addr.get("cep"),
        "street": addr.get("street"),
        "number": addr.get("number"),
        "complement": addr.get("complement"),
        "neighborhood": addr.get("neighborhood"),
        "city": addr.get("city"),
        "state": addr.get("state"),
        "has_proof": bool(entity.get("proof_file")),
        "proof_file": entity.get("proof_file"),
    }


async def check_cep(cep: str) -> dict:
    async with _client() as http:
        return await AddressClient(http).check_cep(cep)


async def save_address(session: AsyncSession, external_id: str, payload: AddressPostRequest) -> str:
    """Cria o endereco, vincula por CEP e avanca address -> documents."""
    async with _client() as http:
        client = AddressClient(http)
        await client.create_address(
            street=payload.street,
            number=payload.number,
            complement=payload.complement,
            neighborhood=payload.neighborhood,
            city=payload.city,
            state=payload.state,
            cep=payload.cep,
        )
        await client.update_entity_cep(ENTITY_TYPE, external_id, payload.cep)

    candidate = await candidate_svc.get(session, external_id)
    if not candidate:
        raise NotFound("Candidato nao encontrado")
    candidate_svc.advance(candidate, CandidateStatus.ADDRESS, CandidateStatus.DOCUMENTS)
    return candidate.status
