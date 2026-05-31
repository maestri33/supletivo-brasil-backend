"""
Reusable FastAPI dependencies.
"""

from collections.abc import AsyncIterator

from app.integrations.http_client import get_http_client


async def http_client_dep() -> AsyncIterator:
    """Provide a shared httpx.AsyncClient."""
    async for client in get_http_client():
        yield client
