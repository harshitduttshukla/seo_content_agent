"""Live-database tests for ContentCard.planned_at and the "new" rule (V3 §5.1).

Each step commits its own transaction, as separate user actions would, so the
database ``now()`` of each step is a distinct, increasing instant.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from app.domains.content_cards.models import ContentCard, ContentCardState
from app.domains.projects.service import ProjectService, is_added_after_plan_lock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.integration import test_v3_plan_lock as lock_tests
from tests.integration import test_v3_strategy_map_isolation as isolation

pytestmark = pytest.mark.integration

DATABASE_URL = isolation.DATABASE_URL
db_engine = isolation.db_engine
session_factory = isolation.session_factory
owner_factory = lock_tests.owner_factory
tenants = lock_tests.tenants


@pytest_asyncio.fixture
async def alpha(tenants: tuple[dict[str, Any], dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    yield tenants[0]


async def _create(
    factory: async_sessionmaker[AsyncSession], tenant: dict[str, Any], state: str
) -> UUID:
    card_id = uuid4()
    async with factory() as session:
        session.add(
            ContentCard(
                id=card_id,
                organization_id=tenant["org_id"],
                project_id=tenant["project_id"],
                kind="cluster",
                state=state,
                origin="plan",
                title=f"card {state}",
            )
        )
        await session.commit()
    return card_id


async def _move(factory: async_sessionmaker[AsyncSession], card_id: UUID, state: str) -> None:
    await asyncio.sleep(0.01)  # a later transaction, so a later now()
    async with factory() as session:
        card = await session.get(ContentCard, card_id)
        assert card is not None
        card.state = state
        await session.commit()


async def _card(factory: async_sessionmaker[AsyncSession], card_id: UUID) -> ContentCard:
    async with factory() as session:
        card = await session.scalar(select(ContentCard).where(ContentCard.id == card_id))
        assert card is not None
        return card


async def _lock(factory: async_sessionmaker[AsyncSession], tenant: dict[str, Any]) -> Any:
    await asyncio.sleep(0.01)
    async with factory() as session:
        state = await ProjectService().lock_plan(
            session,
            actor=tenant["actor"],
            organization_id=tenant["org_id"],
            project_id=tenant["project_id"],
            request_id="test-planned-at",
        )
    return state.plan_locked_at


@pytest.mark.asyncio
async def test_card_created_as_planned_gets_planned_at(
    owner_factory: async_sessionmaker[AsyncSession], alpha: dict[str, Any]
) -> None:
    card = await _card(owner_factory, await _create(owner_factory, alpha, "planned"))
    assert card.planned_at is not None
    assert card.planned_at == card.created_at  # same transaction, same now()


@pytest.mark.asyncio
async def test_backlog_card_planned_after_the_lock_is_new(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    alpha: dict[str, Any],
) -> None:
    """The regression: created before the lock, entered Planned after it."""
    card_id = await _create(owner_factory, alpha, "backlog")
    created = await _card(owner_factory, card_id)
    assert created.planned_at is None

    locked_at = await _lock(session_factory, alpha)
    await _move(owner_factory, card_id, ContentCardState.PLANNED)

    card = await _card(owner_factory, card_id)
    assert card.created_at < locked_at < card.planned_at
    assert is_added_after_plan_lock(card.planned_at, locked_at) is True
    # The old rule would have said "not new" here.
    assert not card.created_at > locked_at


@pytest.mark.asyncio
async def test_card_planned_before_the_lock_is_not_new(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    alpha: dict[str, Any],
) -> None:
    card_id = await _create(owner_factory, alpha, "planned")
    locked_at = await _lock(session_factory, alpha)
    card = await _card(owner_factory, card_id)
    assert card.planned_at < locked_at
    assert is_added_after_plan_lock(card.planned_at, locked_at) is False


@pytest.mark.asyncio
async def test_leaving_planned_keeps_planned_at(
    owner_factory: async_sessionmaker[AsyncSession], alpha: dict[str, Any]
) -> None:
    card_id = await _create(owner_factory, alpha, "planned")
    before = (await _card(owner_factory, card_id)).planned_at

    await _move(owner_factory, card_id, ContentCardState.BUNDLED)

    after = await _card(owner_factory, card_id)
    assert after.state == "bundled"
    assert after.planned_at == before


@pytest.mark.asyncio
async def test_re_entering_planned_restamps_planned_at(
    owner_factory: async_sessionmaker[AsyncSession], alpha: dict[str, Any]
) -> None:
    """planned → backlog → planned is legal (VALID_STATE_TRANSITIONS)."""
    card_id = await _create(owner_factory, alpha, "planned")
    first = (await _card(owner_factory, card_id)).planned_at

    await _move(owner_factory, card_id, ContentCardState.BACKLOG)
    assert (await _card(owner_factory, card_id)).planned_at == first
    await _move(owner_factory, card_id, ContentCardState.PLANNED)

    second = (await _card(owner_factory, card_id)).planned_at
    assert first is not None and second is not None
    assert second > first


@pytest.mark.asyncio
async def test_cards_from_before_the_column_read_as_null_and_never_new(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    alpha: dict[str, Any],
) -> None:
    # The seeded imported card was written with no planned_at, like a legacy row.
    async with owner_factory() as session:
        legacy = await session.scalar(
            select(ContentCard).where(ContentCard.project_id == alpha["project_id"])
        )
    assert legacy is not None and legacy.planned_at is None
    locked_at = await _lock(session_factory, alpha)
    assert is_added_after_plan_lock(legacy.planned_at, locked_at) is False
