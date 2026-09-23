"""Live-database checks for the numbers the V3 strategy map reports.

The unit suite mocks the repository, so it cannot see foreign-key behaviour, the
count the Demand tab lands on, or how many SQL statements actually run. These
tests seed a real tenant in PostgreSQL and read those numbers back.
"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from app.domains.canvas.map_service import StrategyMapService
from app.domains.canvas.models import Area
from app.domains.content_cards.models import ContentCard
from app.domains.demand.models import DemandNode, DemandNodeOrigin, DemandNodeStatus
from app.domains.demand.service import DemandService
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from tests.integration import test_v3_strategy_map_isolation as isolation

# Reuse the isolation module's seed data and its non-owner (RLS-enforced) fixtures.
DATABASE_URL = isolation.DATABASE_URL
_seed = isolation._seed
_tenant_rows = isolation._tenant_rows
db_engine = isolation.db_engine
session_factory = isolation.session_factory

pytestmark = pytest.mark.integration


async def _cleanup(session: AsyncSession, tenant: dict[str, Any]) -> None:
    for statement in (
        "DELETE FROM content_cards WHERE project_id = :p",
        "DELETE FROM demand_nodes WHERE project_id = :p",
        "DELETE FROM claims WHERE project_id = :p",
        "DELETE FROM areas WHERE parent_id IS NOT NULL AND project_id = :p",
        "DELETE FROM areas WHERE project_id = :p",
        "DELETE FROM arguments WHERE project_id = :p",
        "DELETE FROM canvases WHERE parent_id IS NOT NULL AND project_id = :p",
        "DELETE FROM canvases WHERE project_id = :p",
        "DELETE FROM project_members WHERE project_id = :p",
        "DELETE FROM projects WHERE id = :p",
    ):
        await session.execute(text(statement), {"p": tenant["project_id"]})
    await session.execute(
        text("DELETE FROM organization_members WHERE organization_id = :o"),
        {"o": tenant["org_id"]},
    )
    await session.execute(text("DELETE FROM organizations WHERE id = :o"), {"o": tenant["org_id"]})
    await session.execute(text("DELETE FROM users WHERE id = :u"), {"u": tenant["user_id"]})


@pytest_asyncio.fixture
async def owner_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Superuser sessions for seeding and for deleting rows behind the service's back."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def tenant(
    owner_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[dict[str, Any]]:
    rows = _tenant_rows("Count")
    async with owner_factory() as session:
        await _seed(session, rows)
        await session.commit()
    try:
        yield rows
    finally:
        async with owner_factory() as session:
            await _cleanup(session, rows)
            await session.commit()


async def _map(factory: async_sessionmaker[AsyncSession], rows: dict[str, Any]) -> Any:
    async with factory() as session:
        return await StrategyMapService(session).get_strategy_map(
            rows["org_id"], rows["project_id"], actor=rows["actor"]
        )


@pytest.mark.asyncio
async def test_card_on_a_deleted_area_becomes_unassigned_instead_of_vanishing(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenant: dict[str, Any],
) -> None:
    before = await _map(session_factory, tenant)
    assert before.company_canvas.areas[0].children[0].card_count == 1
    assert before.unassigned_card_count == 0

    async with owner_factory() as session:
        await session.execute(text("DELETE FROM areas WHERE id = :a"), {"a": tenant["sub_area_id"]})
        await session.commit()
        card_area = await session.scalar(
            text("SELECT area_id FROM content_cards WHERE project_id = :p"),
            {"p": tenant["project_id"]},
        )
    assert card_area is None  # ON DELETE SET NULL

    after = await _map(session_factory, tenant)
    assert after.company_canvas.areas[0].children == []
    assert after.unassigned_card_count == 1


@pytest.mark.asyncio
async def test_demand_landing_count_equals_the_map_rows_count(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenant: dict[str, Any],
) -> None:
    """The map links to Demand with area + status=kept; both must report the same number."""
    async with owner_factory() as session:
        # A discarded node on the same area: status=all would land on 2, not 1.
        session.add(
            DemandNode(
                id=uuid4(),
                organization_id=tenant["org_id"],
                project_id=tenant["project_id"],
                type="keyword",
                text="Count discarded keyword",
                area_id=tenant["sub_area_id"],
                status=DemandNodeStatus.DISCARDED,
                origin=DemandNodeOrigin.UPLOAD,
            )
        )
        await session.commit()

    result = await _map(session_factory, tenant)
    row = result.company_canvas.areas[0].children[0]

    async with session_factory() as session:
        landed = await DemandService(session).list_nodes(
            tenant["org_id"],
            tenant["project_id"],
            status="kept",
            area_id=row.id,
            page=1,
            page_size=100,
            actor=tenant["actor"],
        )

    assert len(landed.items) == row.demand_count == 1


@pytest.mark.asyncio
async def test_sql_statement_count_does_not_grow_with_the_number_of_areas(
    db_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenant: dict[str, Any],
) -> None:
    """Counts real statements on the wire, so an N+1 anywhere in the path shows up."""
    statements: list[str] = []

    def record(*args: Any) -> None:
        statements.append(args[2])

    async def add_areas(count: int) -> None:
        async with owner_factory() as session:
            for index in range(count):
                session.add(
                    Area(
                        id=uuid4(),
                        organization_id=tenant["org_id"],
                        project_id=tenant["project_id"],
                        canvas_id=tenant["canvas_id"],
                        parent_id=None,
                        name=f"Extra area {index:03d}",
                    )
                )
            await session.commit()

    async def statements_for_map() -> tuple[int, int]:
        statements.clear()
        event.listen(db_engine.sync_engine, "before_cursor_execute", record)
        try:
            result = await _map(session_factory, tenant)
        finally:
            event.remove(db_engine.sync_engine, "before_cursor_execute", record)
        return len(statements), len(result.company_canvas.areas)

    await add_areas(2)  # the seeded root area plus 2 = 3 root areas
    small, small_areas = await statements_for_map()
    await add_areas(197)  # 200 root areas
    large, large_areas = await statements_for_map()

    assert (small_areas, large_areas) == (3, 200)
    assert small > 0  # the listener saw the traffic
    assert small == large


@pytest.mark.asyncio
async def test_card_count_is_every_state_and_parent_shows_descendant_states(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenant: dict[str, Any],
) -> None:
    """The seeded sub-area holds one live card; add one card per other state beside it."""
    extra_states = ["backlog", "planned", "drafting", "qa_passed", "approved"]
    async with owner_factory() as session:
        for state in extra_states:
            session.add(
                ContentCard(
                    id=uuid4(),
                    organization_id=tenant["org_id"],
                    project_id=tenant["project_id"],
                    kind="cluster",
                    area_id=tenant["sub_area_id"],
                    state=state,
                    origin="plan",
                    title=f"Count {state} card",
                )
            )
        await session.commit()

    result = await _map(session_factory, tenant)
    parent = result.company_canvas.areas[0]
    sub_area = parent.children[0]

    assert sub_area.card_count == 6
    assert sub_area.card_states == {state: 1 for state in [*extra_states, "live"]}
    # The parent holds no card itself; its sub-area's states surface on it, and
    # with no demand of its own it is not a gap.
    assert parent.card_count == 0
    assert parent.descendant_card_states == sub_area.card_states
    assert parent.content_gap is False
