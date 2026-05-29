"""Base de integrações HTTP — espelha o padrão de `lead/app/integrations`.

`BaseClient` recebe um `httpx.AsyncClient` já configurado (base_url + timeout) e
`request_with_retry` faz retry com backoff em erros de transporte/5xx.
"""

import asyncio

import httpx
import structlog

logger = structlog.get_logger()


class IntegrationError(Exception):
    """Erro em chamada a serviço externo."""


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int = 3,
    **kwargs,
) -> httpx.Response:
    """Request HTTP com retry e log estruturado.

    Retenta em erros de transporte/timeout e em respostas 5xx; 4xx propaga
    imediatamente (não adianta retentar). Backoff exponencial assíncrono.
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
                "integration_retry", method=method, url=url, attempt=attempt, error=str(exc)
            )
        if attempt < max_retries:
            await asyncio.sleep(2**attempt * 0.1)
    raise IntegrationError(f"{method} {url} failed after {max_retries} attempts") from last_exc


class BaseClient:
    """Cliente base — recebe um httpx.AsyncClient."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.log = logger.bind(integration=self.__class__.__name__)
