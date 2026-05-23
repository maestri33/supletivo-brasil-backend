"""Integração ViaCEP — lookup de CEP brasileiro.

Portado do código original (LOCAL). Distingue dois casos:
- CEP inexistente / formato inválido  -> retorna None (o chamador decide).
- ViaCEP indisponível (rede/HTTP)     -> levanta IntegrationError (502).
"""

import re

import httpx

from app.config import get_settings
from app.exceptions import IntegrationError
from app.utils.logging import get_logger

settings = get_settings()
log = get_logger(__name__)


async def lookup(zipcode: str) -> dict | None:
    """Consulta a ViaCEP e devolve campos normalizados.

    Retorna None se o CEP não existir ou tiver formato inválido. Levanta
    IntegrationError se a ViaCEP estiver indisponível (rede ou status != 200).

    Chaves de retorno (alinhadas ao modelo `addresses`): zipcode, street,
    complement, neighborhood, city, state.
    """
    clean = re.sub(r"\D", "", zipcode or "")
    if len(clean) != 8:
        return None

    url = f"{settings.viacep_base_url.rstrip('/')}/ws/{clean}/json/"
    try:
        async with httpx.AsyncClient(timeout=settings.viacep_timeout_seconds) as client:
            resp = await client.get(url)
    except Exception as exc:
        log.warning("viacep.request_failed", zipcode=clean)
        raise IntegrationError("ViaCEP indisponível no momento") from exc

    if resp.status_code != 200:
        log.warning("viacep.bad_status", zipcode=clean, status=resp.status_code)
        raise IntegrationError(f"ViaCEP retornou status {resp.status_code}")

    data = resp.json()
    if data.get("erro"):
        return None

    return {
        "zipcode": clean,
        "street": data.get("logradouro") or None,
        "complement": data.get("complemento") or None,
        "neighborhood": data.get("bairro") or None,
        "city": data.get("localidade") or None,
        "state": data.get("uf") or None,
    }
