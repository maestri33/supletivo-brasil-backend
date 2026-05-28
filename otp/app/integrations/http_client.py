"""
Async HTTP client for communicating with other microservices.

- Async (httpx).
- Simple retry with exponential backoff for transient errors.
- Sensible default timeout.
- For EACH external service, create a wrapper in
  `app/integrations/<service>_client.py` that uses this client and exposes
  high-level functions — do NOT scatter httpx.get(...) throughout the code.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.exceptions import IntegrationError
from app.utils.logging import get_logger

log = get_logger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
RETRYABLE_STATUS = {429, 502, 503, 504}


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Yield an AsyncClient — use as FastAPI Depends()."""
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        yield client


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_attempts: int = 3,
    backoff_base: float = 0.5,
    **kwargs: Any,
) -> httpx.Response:
    """Make a request with exponential retry on transient errors."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code in RETRYABLE_STATUS and attempt < max_attempts:
                log.warning(
                    "http.retry",
                    method=method,
                    url=url,
                    status=resp.status_code,
                    attempt=attempt,
                )
                await asyncio.sleep(backoff_base * 2 ** (attempt - 1))
                continue
            return resp
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            log.warning("http.transport_error", url=url, attempt=attempt, error=str(exc))
            if attempt == max_attempts:
                raise IntegrationError(f"Failed to call {url}: {exc}") from exc
            await asyncio.sleep(backoff_base * 2 ** (attempt - 1))
    raise IntegrationError(f"Failed to call {url}: {last_exc}")
