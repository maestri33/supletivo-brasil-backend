"""Fixtures globais — staff (milestone 1: sem DB). Testes usam ASGITransport.

Auth gate tests nao precisam de engine/DB (milestone 1):
- sem token → 403
- token invalido → 401
Milestone 1 nao testa caminho feliz (precisa de JWKS real).
"""

from __future__ import annotations

import os

# `DATABASE_URL` e obrigatorio (sem default no codigo). Placeholder
# so permite importar app.config/app.db.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://v7m:v7m@localhost:5432/v7m")
os.environ.setdefault("JWT_BASE_URL", "http://localhost:8080")

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTP client com ASGITransport (sem DB no milestone 1)."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
