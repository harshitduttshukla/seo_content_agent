"""Live-database tests for V3 "Lock plan" persistence (projects.plan_locked_at).

Runs ProjectService.lock_plan as the non-owner ``seo_content_app`` role against
two seeded tenants and reads the rows back as the owner.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from app.core.errors import PermissionDenied, ResourceNotFound
from app.domains.projects.service import ProjectService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.integration import test_v3_strategy_map_isolation as isolation

pytestmark = pytest.mark.integration

DATABASE_URL = isolation.DATABASE_URL
db_engine = isolation.db_engine
session_factory = isolation.session_factory

WRITER_ROLE_ID = UUID("00000000-0000-0000-0000-000000000004")  # content.write, no project.update
VIEWER_ROLE_ID = UUID("00000000-0000-0000-0000-000000000006")


@pytest_asyncio.fixture
async def owner_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(DATABASE_URL, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def tenants(
    owner_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[tuple[dict[str, Any], dict[str, Any]]]:
    alpha, bravo = isolation._tenant_rows("Alpha"), isolation._tenant_rows("Bravo")
    async with owner_factory() as session:
        for tenant in (alpha, bravo):
            await isolation._seed(session, tenant)
        await session.commit()
    try:
        yield alpha, bravo
    finally:
        async with owner_factory() as session:
            for tenant in (alpha, bravo):
                params = {"p": tenant["project_id"], "o": tenant["org_id"]}
                for statement in (
                    "DELETE FROM audit_logs WHERE project_id = :p",
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
                    "DELETE FROM organization_members WHERE organization_id = :o",
                    "DELETE FROM organizations WHERE id = :o",
                ):
                    await session.execute(text(statement), params)
                await session.execute(
                    text("DELETE FROM users WHERE id = :u"), {"u": tenant["user_id"]}
                )
            await session.commit()


async def _project_row(factory: async_sessionmaker[AsyncSession], tenant: dict[str, Any]) -> Any:
    async with factory() as session:
        return (
            (
                await session.execute(
                    text("SELECT * FROM projects WHERE id = :p"), {"p": tenant["project_id"]}
                )
            )
            .one()
            ._asdict()
        )


async def _lock(
    factory: async_sessionmaker[AsyncSession],
    tenant: dict[str, Any],
    *,
    organization_id: UUID | None = None,
    project_id: UUID | None = None,
) -> Any:
    async with factory() as session:
        return await ProjectService().lock_plan(
            session,
            actor=tenant["actor"],
            organization_id=organization_id or tenant["org_id"],
            project_id=project_id or tenant["project_id"],
            request_id="test-plan-lock",
        )


async def _set_role(
    factory: async_sessionmaker[AsyncSession], tenant: dict[str, Any], role_id: UUID
) -> None:
    async with factory() as session:
        for table in ("organization_members", "project_members"):
            await session.execute(
                text(f"UPDATE {table} SET role_id = :r WHERE user_id = :u"),
                {"r": role_id, "u": tenant["user_id"]},
            )
        await session.commit()


@pytest.mark.asyncio
async def test_a_new_project_is_unlocked(
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = tenants
    assert (await _project_row(owner_factory, alpha))["plan_locked_at"] is None


@pytest.mark.asyncio
async def test_first_lock_sets_a_database_timestamp_and_changes_nothing_else(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = tenants
    before = await _project_row(owner_factory, alpha)
    async with owner_factory() as session:
        db_before = await session.scalar(text("SELECT now()"))

    state = await _lock(session_factory, alpha)

    async with owner_factory() as session:
        db_after = await session.scalar(text("SELECT now()"))
    after = await _project_row(owner_factory, alpha)
    assert state.locked_now is True
    assert state.plan_locked_at == after["plan_locked_at"]
    assert db_before <= after["plan_locked_at"] <= db_after  # the database clock
    assert {k: v for k, v in after.items() if k != "plan_locked_at"} == {
        k: v for k, v in before.items() if k != "plan_locked_at"
    }


@pytest.mark.asyncio
async def test_locking_again_keeps_the_original_timestamp(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = tenants
    first = await _lock(session_factory, alpha)
    await asyncio.sleep(0.01)
    second = await _lock(session_factory, alpha)

    assert (first.locked_now, second.locked_now) == (True, False)
    assert second.plan_locked_at == first.plan_locked_at
    assert (await _project_row(owner_factory, alpha))["plan_locked_at"] == first.plan_locked_at


@pytest.mark.asyncio
async def test_concurrent_locks_persist_exactly_one_timestamp(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = tenants
    results = await asyncio.gather(*(_lock(session_factory, alpha) for _ in range(5)))

    assert sum(result.locked_now for result in results) == 1
    assert len({result.plan_locked_at for result in results}) == 1
    stored = (await _project_row(owner_factory, alpha))["plan_locked_at"]
    assert results[0].plan_locked_at == stored
    async with owner_factory() as session:
        audits = await session.scalar(
            text(
                "SELECT count(*) FROM audit_logs WHERE project_id = :p "
                "AND action = 'project.plan_locked'"
            ),
            {"p": alpha["project_id"]},
        )
    assert audits == 1


@pytest.mark.asyncio
async def test_locking_one_project_never_touches_another(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, bravo = tenants
    bravo_before = await _project_row(owner_factory, bravo)

    await _lock(session_factory, alpha)

    assert await _project_row(owner_factory, bravo) == bravo_before
    assert bravo_before["plan_locked_at"] is None


@pytest.mark.asyncio
async def test_a_user_cannot_lock_another_tenants_project(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, bravo = tenants
    for organization_id in (bravo["org_id"], alpha["org_id"]):
        with pytest.raises((ResourceNotFound, PermissionDenied)):
            await _lock(
                session_factory,
                alpha,
                organization_id=organization_id,
                project_id=bravo["project_id"],
            )
    # And pairing Alpha's project with Bravo's organization id is refused too.
    with pytest.raises((ResourceNotFound, PermissionDenied)):
        await _lock(session_factory, alpha, organization_id=bravo["org_id"])

    assert (await _project_row(owner_factory, bravo))["plan_locked_at"] is None
    assert (await _project_row(owner_factory, alpha))["plan_locked_at"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("role_id", [WRITER_ROLE_ID, VIEWER_ROLE_ID])
async def test_roles_without_project_update_cannot_lock(
    role_id: UUID,
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = tenants
    await _set_role(owner_factory, alpha, role_id)

    with pytest.raises(PermissionDenied):
        await _lock(session_factory, alpha)
    assert (await _project_row(owner_factory, alpha))["plan_locked_at"] is None
