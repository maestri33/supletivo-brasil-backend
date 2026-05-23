"""Fixtures globais dos testes."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app as fastapi_app


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client():
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
