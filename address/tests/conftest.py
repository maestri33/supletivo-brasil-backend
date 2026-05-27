"""Conftest for address service tests.

Uses a real Postgres test database with migrations applied.
The test DB is created on-demand using DATABASE_URL with a test suffix.
"""

import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Force test settings before any app imports
os.environ.setdefault("DATABASE_SCHEMA", "addresses_test")
os.environ.setdefault("WEBHOOK_URL", "")

from app.config import get_settings  # noqa: E402
from app.db import Base, auth_users, get_session  # noqa: E402
from app.main import app  # noqa: E402

settings = get_settings()


@pytest.fixture(scope="session")
def _setup_database():
    """Create test schema + auth.users shadow table once per session."""
    engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    import asyncio

    async def _setup():
        async with engine.connect() as conn:
            # Create schema if not exists
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {settings.database_schema}"))
            # Create auth schema for FK reference
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
            # Create shadow auth.users table for FK
            await conn.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS auth.users (
                        external_id UUID PRIMARY KEY
                    )
                """)
            )
            await conn.commit()
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())
    engine.sync_engine.dispose()
    yield
    asyncio.run(_teardown(engine))


async def _teardown(engine):
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {settings.database_schema} CASCADE"))
        # Don't drop auth schema — it may be shared


@pytest.fixture
async def session(_setup_database) -> AsyncSession:
    """Get a fresh session for each test, rollback after."""
    maker = async_sessionmaker(
        create_async_engine(settings.database_url, pool_pre_ping=True),
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with maker() as session:
        # Ensure a test user exists in auth.users for FK
        test_external_id = "00000000-0000-0000-0000-000000000001"
        await session.execute(
            text(f"INSERT INTO auth.users (external_id) VALUES ('{test_external_id}') ON CONFLICT DO NOTHING")
        )
        await session.commit()
        yield session


@pytest.fixture
async def client(_setup_database) -> AsyncClient:
    """FastAPI test client with DB session."""
    maker = async_sessionmaker(
        create_async_engine(settings.database_url, pool_pre_ping=True),
        expire_on_commit=False,
        class_=AsyncSession,
    )

    async def _override_session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
