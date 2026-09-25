"""Live-database tests for the V3 Content Hub plan board (§5.1).

Runs ContentHubService as the non-owner ``seo_content_app`` role, so RLS is
enforced, against two seeded tenants. Each tenant's seed carries one imported
live card; tests add the cards they need.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from app.core.errors import ConflictError, PermissionDenied, ResourceNotFound
from app.domains.content_cards.hub_service import ContentHubService
from app.domains.content_cards.models import ContentCard
from app.domains.content_cards.schemas import (
    BoardFilters,
    BoardMoveRequest,
    ContentCardKind,
    ContentHubBoard,
    PlannedOrderRequest,
)
from app.domains.projects.service import ProjectService
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.integration import test_v3_plan_lock as lock_tests
from tests.integration import test_v3_strategy_map_isolation as isolation

pytestmark = pytest.mark.integration

DATABASE_URL = isolation.DATABASE_URL
db_engine = isolation.db_engine
session_factory = isolation.session_factory
owner_factory = lock_tests.owner_factory
tenants = lock_tests.tenants

ALL_STATES = (
    "backlog",
    "planned",
    "bundled",
    "outlined",
    "drafting",
    "qa_failed",
    "qa_passed",
    "approved",
)


@pytest_asyncio.fixture
async def pair(
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> AsyncIterator[tuple[dict[str, Any], dict[str, Any]]]:
    yield tenants


async def _create(
    factory: async_sessionmaker[AsyncSession],
    tenant: dict[str, Any],
    state: str,
    **fields: Any,
) -> UUID:
    card_id = uuid4()
    async with factory() as session:
        session.add(
            ContentCard(
                id=card_id,
                organization_id=tenant["org_id"],
                project_id=tenant["project_id"],
                kind=fields.pop("kind", "cluster"),
                state=state,
                origin="plan",
                title=fields.pop("title", f"{tenant['label']} {state}"),
                **fields,
            )
        )
        await session.commit()
    return card_id


async def _board(
    factory: async_sessionmaker[AsyncSession],
    tenant: dict[str, Any],
    filters: BoardFilters | None = None,
    *,
    project_id: UUID | None = None,
) -> ContentHubBoard:
    async with factory() as session:
        return await ContentHubService(session).get_board(
            tenant["org_id"],
            project_id or tenant["project_id"],
            filters or BoardFilters(),
            actor=tenant["actor"],
        )


async def _move(
    factory: async_sessionmaker[AsyncSession],
    tenant: dict[str, Any],
    card_id: UUID,
    target: str,
    revision: int,
    *,
    organization_id: UUID | None = None,
    project_id: UUID | None = None,
) -> Any:
    async with factory() as session:
        return await ContentHubService(session).move_card(
            organization_id or tenant["org_id"],
            project_id or tenant["project_id"],
            card_id,
            BoardMoveRequest(target_state=target, revision=revision),  # type: ignore[arg-type]
            actor=tenant["actor"],
            request_id="test-board-move",
        )


async def _reorder(
    factory: async_sessionmaker[AsyncSession],
    tenant: dict[str, Any],
    card_ids: list[UUID],
    *,
    project_id: UUID | None = None,
) -> ContentHubBoard:
    async with factory() as session:
        return await ContentHubService(session).reorder_planned(
            tenant["org_id"],
            project_id or tenant["project_id"],
            PlannedOrderRequest(card_ids=card_ids),
            actor=tenant["actor"],
            request_id="test-board-reorder",
        )


async def _row(factory: async_sessionmaker[AsyncSession], card_id: UUID) -> ContentCard:
    async with factory() as session:
        card = await session.scalar(select(ContentCard).where(ContentCard.id == card_id))
        assert card is not None
        return card


def _ids(board: ContentHubBoard, key: str) -> list[UUID]:
    return [card.id for card in next(c for c in board.columns if c.key == key).cards]


# ── Board read ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_every_state_lands_in_its_column_once_with_matching_counts(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    created = {state: await _create(owner_factory, alpha, state) for state in ALL_STATES}

    board = await _board(session_factory, alpha)

    assert [column.key for column in board.columns] == [
        "backlog", "planned", "outline", "draft", "review", "approved", "live",
    ]  # fmt: skip
    expected = {
        "backlog": {created["backlog"]},
        "planned": {created["planned"], created["bundled"]},
        "outline": {created["outlined"]},
        "draft": {created["drafting"], created["qa_failed"]},
        "review": {created["qa_passed"]},
        "approved": {created["approved"]},
    }
    for key, ids in expected.items():
        assert set(_ids(board, key)) == ids, key
    assert len(_ids(board, "live")) == 1  # the seeded imported page
    every = [card.id for column in board.columns for card in column.cards]
    assert len(every) == len(set(every)) == board.total_count == len(ALL_STATES) + 1
    for column in board.columns:
        assert column.count == len(column.cards)


@pytest.mark.asyncio
async def test_board_reads_in_a_fixed_number_of_queries(
    db_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair

    async def count_selects(n_cards: int) -> int:
        for _ in range(n_cards):
            await _create(owner_factory, alpha, "planned")
        statements: list[str] = []

        def record(*args: Any) -> None:
            statements.append(str(args[2]))

        event.listen(db_engine.sync_engine, "before_cursor_execute", record)
        try:
            await _board(session_factory, alpha)
        finally:
            event.remove(db_engine.sync_engine, "before_cursor_execute", record)
        return sum(1 for statement in statements if statement.lstrip().upper().startswith("SELECT"))

    few = await count_selects(1)
    many = await count_selects(8)
    assert few == many  # no per-card or per-column queries


@pytest.mark.asyncio
async def test_filters_combine_and_options_come_from_the_whole_project(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    match = await _create(
        owner_factory,
        alpha,
        "backlog",
        kind="compare",
        area_id=alpha["area_id"],
        argument_id=alpha["argument_id"],
        owner=alpha["user_id"],
        market={"lang": "en", "country": "GB"},
    )
    await _create(owner_factory, alpha, "backlog", kind="compare", area_id=alpha["area_id"])
    await _create(
        owner_factory, alpha, "planned", kind="cluster", market={"lang": "en", "country": "GB"}
    )

    board = await _board(
        session_factory,
        alpha,
        BoardFilters(
            area_id=alpha["area_id"],
            kind=ContentCardKind.COMPARE,
            market="en-GB",
            owner_id=alpha["user_id"],
            argument_id=alpha["argument_id"],
        ),
    )

    assert board.total_count == 1
    assert _ids(board, "backlog") == [match]
    card = board.columns[0].cards[0]
    assert card.area is not None and card.area.name == alpha["area_name"]
    assert card.owner is not None and card.owner.name == alpha["actor"].display_name
    options = board.filter_options
    assert {ref.id for ref in options.areas} == {alpha["area_id"], alpha["sub_area_id"]}
    assert set(options.kinds) == {"compare", "cluster"}
    assert "en-GB" in options.markets
    assert [ref.id for ref in options.owners] == [alpha["user_id"]]


# ── Tenant isolation ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_project_a_cannot_read_project_b_board_counts_or_lock(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, bravo = pair
    await _create(owner_factory, bravo, "planned")
    async with session_factory() as session:
        await ProjectService().lock_plan(
            session,
            actor=bravo["actor"],
            organization_id=bravo["org_id"],
            project_id=bravo["project_id"],
            request_id="lock-bravo",
        )

    with pytest.raises((ResourceNotFound, PermissionDenied)):
        await _board(session_factory, alpha, project_id=bravo["project_id"])
    with pytest.raises((ResourceNotFound, PermissionDenied)):
        async with session_factory() as session:
            await ContentHubService(session).get_board(
                bravo["org_id"], bravo["project_id"], BoardFilters(), actor=alpha["actor"]
            )

    own = await _board(session_factory, alpha)
    assert own.plan_locked_at is None  # bravo's lock is invisible
    assert own.total_count == 1
    assert all(card.title.startswith("Alpha") for c in own.columns for card in c.cards)


@pytest.mark.asyncio
async def test_project_a_cannot_move_or_reorder_project_b_cards(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, bravo = pair
    bravo_card = await _create(owner_factory, bravo, "backlog")
    bravo_planned = await _create(owner_factory, bravo, "planned")

    # Bravo's card through alpha's own scope: not found.
    with pytest.raises(ResourceNotFound):
        await _move(session_factory, alpha, bravo_card, "planned", 1)
    # Through bravo's scope with alpha's identity: refused.
    with pytest.raises((ResourceNotFound, PermissionDenied)):
        await _move(
            session_factory,
            alpha,
            bravo_card,
            "planned",
            1,
            organization_id=bravo["org_id"],
            project_id=bravo["project_id"],
        )
    # Alpha has no planned cards, so a bravo id is a mismatch, not a write.
    with pytest.raises(ConflictError):
        await _reorder(session_factory, alpha, [bravo_planned])
    with pytest.raises((ResourceNotFound, PermissionDenied)):
        await _reorder(session_factory, alpha, [bravo_planned], project_id=bravo["project_id"])

    assert (await _row(owner_factory, bravo_card)).state == "backlog"
    assert (await _row(owner_factory, bravo_planned)).priority == 0


# ── Permissions ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_viewer_reads_the_board_but_cannot_move_or_reorder(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    card = await _create(owner_factory, alpha, "backlog")
    planned = await _create(owner_factory, alpha, "planned")
    await lock_tests._set_role(owner_factory, alpha, lock_tests.VIEWER_ROLE_ID)

    assert (await _board(session_factory, alpha)).total_count == 3
    with pytest.raises(PermissionDenied):
        await _move(session_factory, alpha, card, "planned", 1)
    with pytest.raises(PermissionDenied):
        await _reorder(session_factory, alpha, [planned])
    assert (await _row(owner_factory, card)).state == "backlog"


@pytest.mark.asyncio
async def test_writer_without_project_update_can_move_cards(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    card = await _create(owner_factory, alpha, "backlog")
    await lock_tests._set_role(owner_factory, alpha, lock_tests.WRITER_ROLE_ID)
    moved = await _move(session_factory, alpha, card, "planned", 1)
    assert moved.state == "planned"


# ── Moves ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_backlog_to_planned_and_back_with_planned_at_and_revision(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    existing = await _create(owner_factory, alpha, "planned", priority=4)
    card = await _create(owner_factory, alpha, "backlog")
    assert (await _row(owner_factory, card)).planned_at is None

    moved = await _move(session_factory, alpha, card, "planned", 1)
    assert (moved.state, moved.column, moved.revision) == ("planned", "planned", 2)
    assert moved.planned_at is not None
    assert moved.priority == 5  # bottom of Planned
    first_planned_at = moved.planned_at

    back = await _move(session_factory, alpha, card, "backlog", 2)
    assert (back.state, back.revision) == ("backlog", 3)
    assert back.planned_at == first_planned_at  # leaving Planned keeps the stamp

    await asyncio.sleep(0.01)
    again = await _move(session_factory, alpha, card, "planned", 3)
    assert again.planned_at is not None and again.planned_at > first_planned_at
    assert (await _row(owner_factory, existing)).priority == 4

    async with owner_factory() as session:
        actions = (
            (
                await session.execute(
                    text(
                        "SELECT action FROM audit_logs WHERE resource_id = :c ORDER BY occurred_at"
                    ),
                    {"c": card},
                )
            )
            .scalars()
            .all()
        )
    assert actions == ["content_card.state_changed"] * 3


@pytest.mark.asyncio
async def test_stale_revision_is_a_conflict_and_writes_nothing(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    card = await _create(owner_factory, alpha, "backlog", revision=5)
    with pytest.raises(ConflictError) as raised:
        await _move(session_factory, alpha, card, "planned", 4)
    assert raised.value.code == "VERSION_CONFLICT"
    row = await _row(owner_factory, card)
    assert (row.state, row.revision, row.planned_at) == ("backlog", 5, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "target"),
    [
        ("outlined", "backlog"),
        ("qa_passed", "planned"),
        ("live", "backlog"),
        ("bundled", "backlog"),
        ("backlog", "backlog"),
        ("planned", "planned"),
    ],
)
async def test_board_refuses_moves_outside_backlog_and_planned(
    state: str,
    target: str,
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    card = await _create(owner_factory, alpha, state)
    with pytest.raises(ConflictError) as raised:
        await _move(session_factory, alpha, card, target, 1)
    assert raised.value.code == "BOARD_MOVE_NOT_ALLOWED"
    row = await _row(owner_factory, card)
    assert (row.state, row.revision) == (state, 1)


# ── Planned ordering ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reorder_sets_priority_one_to_n_and_the_board_follows_it(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    a = await _create(owner_factory, alpha, "planned", priority=1)
    b = await _create(owner_factory, alpha, "planned", priority=2)
    c = await _create(owner_factory, alpha, "bundled", priority=3)
    assert _ids(await _board(session_factory, alpha), "planned") == [a, b, c]

    board = await _reorder(session_factory, alpha, [c, a, b])

    assert _ids(board, "planned") == [c, a, b]
    assert [(await _row(owner_factory, i)).priority for i in (c, a, b)] == [1, 2, 3]
    assert [(await _row(owner_factory, i)).revision for i in (c, a, b)] == [2, 2, 2]
    assert _ids(await _board(session_factory, alpha), "planned") == [c, a, b]


@pytest.mark.asyncio
async def test_reorder_refuses_incomplete_duplicate_or_non_planned_lists(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    a = await _create(owner_factory, alpha, "planned", priority=1)
    b = await _create(owner_factory, alpha, "planned", priority=2)
    backlog = await _create(owner_factory, alpha, "backlog")

    for card_ids in ([a], [a, a, b], [a, b, backlog], [backlog]):
        with pytest.raises(ConflictError) as raised:
            await _reorder(session_factory, alpha, card_ids)
        assert raised.value.code == "PLANNED_ORDER_MISMATCH"
    assert [(await _row(owner_factory, i)).priority for i in (a, b)] == [1, 2]


# ── Plan lock and the "new" chip ──────────────────────────────────


@pytest.mark.asyncio
async def test_new_chip_follows_planned_at_against_the_lock(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    before = await _create(owner_factory, alpha, "planned")
    old_backlog = await _create(owner_factory, alpha, "backlog")  # created before the lock

    board = await _board(session_factory, alpha)
    assert board.plan_locked_at is None
    assert not any(card.is_new_after_plan_lock for c in board.columns for card in c.cards)

    await asyncio.sleep(0.01)
    async with session_factory() as session:
        lock = await ProjectService().lock_plan(
            session,
            actor=alpha["actor"],
            organization_id=alpha["org_id"],
            project_id=alpha["project_id"],
            request_id="lock-alpha",
        )
    await asyncio.sleep(0.01)
    after = await _create(owner_factory, alpha, "planned")
    moved = await _move(session_factory, alpha, old_backlog, "planned", 1)
    assert moved.is_new_after_plan_lock is True  # created before, planned after

    board = await _board(session_factory, alpha)
    assert board.plan_locked_at == lock.plan_locked_at
    new = {card.id: card.is_new_after_plan_lock for card in board.columns[1].cards}
    assert new == {before: False, after: True, old_backlog: True}
