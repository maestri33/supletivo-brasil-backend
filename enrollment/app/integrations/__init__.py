"""Base de integrações HTTP — cliente base + retry exponencial assíncrono.

Espelha o padrão do `candidate/app/integrations/__init__.py`: 4xx propaga
(`HTTPStatusError`); 5xx/transporte tenta novamente com backoff exponencial e,
esgotadas as tentativas, levanta `IntegrationError` (502 no handler).
"""

import asyncio

import httpx

from app.exceptions import IntegrationError
from app.utils.logging import get_logger

logger = get_logger("enrollment.integrations")


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int = 3,
    **kwargs,
) -> httpx.Response:
    """Request HTTP com retry exponencial (só em 5xx/transporte) e log estruturado.

    4xx não é retentado: levanta `httpx.HTTPStatusError` para o chamador tratar
    (mapeado em `api/errors.py:upstream_errors` para HTTPException de mesmo status).
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = await client.request(method, url, **kwargs)
            logger.info(
                "integration_call",
                method=method,
                url=url,
                status=resp.status_code,
                attempt=attempt,
            )
            if resp.is_success:
                return resp
            if resp.status_code < 500:
                resp.raise_for_status()
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            logger.warning(
                "integration_retry",
                method=method,
                url=url,
                attempt=attempt,
                error=str(exc),
            )
        if attempt < max_retries:
            # backoff exponencial não bloqueante (event loop livre durante a espera)
            await asyncio.sleep(2**attempt * 0.1)
    raise IntegrationError(f"{method} {url} falhou após {max_retries} tentativas") from last_exc


class BaseClient:
    """Cliente base para integrações — recebe um httpx.AsyncClient já configurado."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.log = logger.bind(integration=self.__class__.__name__)
