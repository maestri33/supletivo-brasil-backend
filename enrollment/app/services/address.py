"""Etapa address — orquestra o serviço `address` (CEP + criação).

Vincula o endereço à entidade `enrollment/{external_id}` no serviço address,
seguindo a mesma chave usada nas demais integrações.
"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import NotFound
from app.integrations.address import AddressClient
from app.models import EnrollmentStatus
from app.schemas.address import AddressPostRequest
from app.services import enrollment as enrollment_svc

settings = get_settings()

ENTITY_TYPE = "enrollment"


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
    }


async def check_cep(cep: str) -> dict:
    async with _client() as http:
        return await AddressClient(http).check_cep(cep)


async def save_address(
    session: AsyncSession,
    external_id: str,
    payload: AddressPostRequest,
) -> str:
    """Cria endereço + vincula por CEP + avança profile → address."""
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

    enrollment = await enrollment_svc.get(session, external_id)
    if not enrollment:
        raise NotFound("Matrícula não encontrada")
    enrollment_svc.advance(enrollment, EnrollmentStatus.PROFILE, EnrollmentStatus.ADDRESS)
    return enrollment.status
