"""Integração ViaCEP — lookup de CEP brasileiro.

Portado do código original (LOCAL). Best-effort: erros de rede viram None,
o chamador decide o fallback (ex.: salvar só o zipcode).
"""

import re

import httpx

from app.config import get_settings
from app.utils.logging import get_logger

settings = get_settings()
log = get_logger(__name__)


async def lookup(zipcode: str) -> dict | None:
    """Consulta a ViaCEP e devolve campos normalizados, ou None se falhar/não achar.

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
    except Exception:
        log.warning("viacep.request_failed", zipcode=clean)
        return None

    if resp.status_code != 200:
        log.warning("viacep.bad_status", zipcode=clean, status=resp.status_code)
        return None

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
