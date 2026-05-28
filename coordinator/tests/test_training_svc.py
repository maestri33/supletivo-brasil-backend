"""Tests for training approval service CRUD operations."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training_approval import ApprovalStatus
from app.services import (
    create_coordinator,
    create_training_approval,
    list_training_approvals,
    review_training_approval,
)


@pytest.fixture
async def coordinator(db_session: AsyncSession) -> str:
    c = await create_coordinator(db_session, external_id="ta-ext", hub_external_id="ta-hub")
    await db_session.commit()
    return c.id


class TestCreateTrainingApproval:
    async def test_creates_approval(self, db_session: AsyncSession, coordinator: str) -> None:
        ta = await create_training_approval(
            db_session,
            coordinator_id=coordinator,
            candidate_external_id="cand-001",
            training_external_id="train-001",
        )
        assert ta.id is not None
        assert ta.coordinator_id == coordinator
        assert ta.candidate_external_id == "cand-001"
        assert ta.training_external_id == "train-001"
        assert ta.status == ApprovalStatus.pending

    async def test_flushes_with_id(self, db_session: AsyncSession, coordinator: str) -> None:
        ta = await create_training_approval(
            db_session,
            coordinator_id=coordinator,
            candidate_external_id="cand-002",
            training_external_id="train-002",
        )
        assert ta.id is not None


class TestListTrainingApprovals:
    async def test_returns_all(self, db_session: AsyncSession, coordinator: str) -> None:
        await create_training_approval(
            db_session,
            coordinator_id=coordinator,
            candidate_external_id="cand-l1",
            training_external_id="tr-l1",
        )
        await create_training_approval(
            db_session,
            coordinator_id=coordinator,
            candidate_external_id="cand-l2",
            training_external_id="tr-l2",
        )
        await db_session.commit()

        items, total = await list_training_approvals(db_session)
        assert total == 2
        assert len(items) == 2

    async def test_filters_by_coordinator(self, db_session: AsyncSession, coordinator: str) -> None:
        c2 = await create_coordinator(db_session, external_id="other-ta", hub_external_id="other")
        await db_session.commit()

        await create_training_approval(
            db_session,
            coordinator_id=coordinator,
            candidate_external_id="c1",
            training_external_id="t1",
        )
        await create_training_approval(
            db_session,
            coordinator_id=c2.id,
            candidate_external_id="c2",
            training_external_id="t2",
        )
        await db_session.commit()

        items, total = await list_training_approvals(db_session, coordinator_id=coordinator)
        assert total == 1

    async def test_returns_empty(self, db_session: AsyncSession) -> None:
        items, total = await list_training_approvals(db_session)
        assert total == 0
        assert items == []


class TestReviewTrainingApproval:
    async def test_approves(self, db_session: AsyncSession, coordinator: str) -> None:
        ta = await create_training_approval(
            db_session,
            coordinator_id=coordinator,
            candidate_external_id="cand-r1",
            training_external_id="tr-r1",
        )
        await db_session.commit()

        result = await review_training_approval(db_session, ta.id, approved=True)
        assert result is not None
        assert result.status == ApprovalStatus.approved

    async def test_rejects(self, db_session: AsyncSession, coordinator: str) -> None:
        ta = await create_training_approval(
            db_session,
            coordinator_id=coordinator,
            candidate_external_id="cand-r2",
            training_external_id="tr-r2",
        )
        await db_session.commit()

        result = await review_training_approval(
            db_session, ta.id, approved=False, reason="Not eligible"
        )
        assert result is not None
        assert result.status == ApprovalStatus.rejected
        assert result.reason == "Not eligible"

    async def test_returns_none_for_missing(self, db_session: AsyncSession) -> None:
        result = await review_training_approval(db_session, "no-such", approved=True)
        assert result is None

    async def test_approve_sets_no_reason_when_none_given(
        self, db_session: AsyncSession, coordinator: str
    ) -> None:
        ta = await create_training_approval(
            db_session,
            coordinator_id=coordinator,
            candidate_external_id="cand-r3",
            training_external_id="tr-r3",
        )
        await db_session.commit()

        result = await review_training_approval(db_session, ta.id, approved=True)
        assert result.status == ApprovalStatus.approved
