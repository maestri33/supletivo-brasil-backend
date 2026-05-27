"""Tests for coordinator service CRUD operations."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coordinator import Coordinator, CoordinatorStatus
from app.services import (
    create_coordinator,
    get_coordinator,
    get_coordinator_by_external_id,
    list_coordinators,
    update_coordinator_status,
)


class TestCreateCoordinator:
    async def test_creates_coordinator(self, db_session: AsyncSession) -> None:
        c = await create_coordinator(
            db_session,
            external_id="ext-001",
            hub_external_id="hub-001",
        )
        assert c.id is not None
        assert c.external_id == "ext-001"
        assert c.hub_external_id == "hub-001"
        assert c.status == CoordinatorStatus.active
        assert c.created_at is not None

    async def test_flushes_without_commit(self, db_session: AsyncSession) -> None:
        c = await create_coordinator(
            db_session,
            external_id="ext-002",
            hub_external_id="hub-002",
        )
        # Still in transaction — should have id from flush
        assert c.id is not None


class TestGetCoordinator:
    async def test_returns_coordinator_by_id(self, db_session: AsyncSession) -> None:
        c = await create_coordinator(db_session, external_id="ext-003", hub_external_id="hub-003")
        await db_session.commit()

        found = await get_coordinator(db_session, c.id)
        assert found is not None
        assert found.id == c.id
        assert found.external_id == "ext-003"

    async def test_returns_none_for_missing(self, db_session: AsyncSession) -> None:
        found = await get_coordinator(db_session, "nonexistent-id")
        assert found is None

    async def test_returns_coordinator_by_external_id(self, db_session: AsyncSession) -> None:
        c = await create_coordinator(db_session, external_id="ext-004", hub_external_id="hub-004")
        await db_session.commit()

        found = await get_coordinator_by_external_id(db_session, "ext-004")
        assert found is not None
        assert found.id == c.id

    async def test_by_external_id_returns_none(self, db_session: AsyncSession) -> None:
        found = await get_coordinator_by_external_id(db_session, "no-such")
        assert found is None


class TestListCoordinators:
    async def test_returns_all(self, db_session: AsyncSession) -> None:
        await create_coordinator(db_session, external_id="ext-005", hub_external_id="hub-005")
        await create_coordinator(db_session, external_id="ext-006", hub_external_id="hub-005")
        await db_session.commit()

        items, total = await list_coordinators(db_session)
        assert total == 2
        assert len(items) == 2

    async def test_filters_by_hub(self, db_session: AsyncSession) -> None:
        await create_coordinator(db_session, external_id="ext-007", hub_external_id="hub-a")
        await create_coordinator(db_session, external_id="ext-008", hub_external_id="hub-b")
        await db_session.commit()

        items, total = await list_coordinators(db_session, hub_external_id="hub-a")
        assert total == 1
        assert items[0].external_id == "ext-007"

    async def test_filters_by_status(self, db_session: AsyncSession) -> None:
        from app.models.coordinator import CoordinatorStatus

        c1 = await create_coordinator(db_session, external_id="ext-009", hub_external_id="hub-x")
        c2 = await create_coordinator(db_session, external_id="ext-010", hub_external_id="hub-x")
        await update_coordinator_status(db_session, c2.id, CoordinatorStatus.inactive)
        await db_session.commit()

        items, total = await list_coordinators(db_session, status=CoordinatorStatus.active.value)
        assert total == 1
        assert items[0].id == c1.id

    async def test_pagination(self, db_session: AsyncSession) -> None:
        for i in range(5):
            await create_coordinator(db_session, external_id=f"ext-p{i}", hub_external_id="hub-p")
        await db_session.commit()

        items, total = await list_coordinators(db_session, offset=0, limit=2)
        assert total == 5
        assert len(items) == 2

    async def test_returns_empty_when_none(self, db_session: AsyncSession) -> None:
        items, total = await list_coordinators(db_session)
        assert total == 0
        assert items == []


class TestUpdateCoordinatorStatus:
    async def test_updates_status(self, db_session: AsyncSession) -> None:
        c = await create_coordinator(db_session, external_id="ext-011", hub_external_id="hub-011")
        await db_session.commit()

        updated = await update_coordinator_status(
            db_session, c.id, CoordinatorStatus.inactive
        )
        assert updated is not None
        assert updated.status == CoordinatorStatus.inactive

    async def test_returns_none_for_missing(self, db_session: AsyncSession) -> None:
        result = await update_coordinator_status(
            db_session, "no-such", CoordinatorStatus.inactive
        )
        assert result is None
