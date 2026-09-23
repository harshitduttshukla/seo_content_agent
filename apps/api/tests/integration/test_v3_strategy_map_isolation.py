"""Tenant-isolation tests for the V3 strategy map.

The map is a read of an entire project graph in one request, which makes it the
exact shape of query that leaks across tenants if any single scope predicate is
missed. These tests seed two complete tenants and assert that nothing belonging
to project B can be reached through project A's map.

Runs against PostgreSQL as the non-superuser ``seo_content_app`` role so the RLS
policies are actually exercised rather than bypassed by the table owner.
"""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from app.core.errors import PermissionDenied, ResourceNotFound
from app.domains.auth.models import OrganizationMember, ProjectMember
from app.domains.canvas.map_service import StrategyMapService
from app.domains.canvas.models import Area, Argument, Canvas, Claim
from app.domains.content_cards.models import ContentCard
from app.domains.demand.models import DemandNode, DemandNodeOrigin, DemandNodeStatus
from app.domains.organizations.models import Organization
from app.domains.projects.models import Project
from app.domains.users.models import User
from app.security.principal import AuthenticatedUser
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

pytestmark = pytest.mark.integration

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/seo_content",
)

MEMBER_ROLE_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    # Non-superuser application role, so RLS is enforced rather than bypassed.
    test_db_url = DATABASE_URL.replace("postgres:postgres", "seo_content_app:seo_content_app")
    engine = create_async_engine(test_db_url, echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


def _tenant_rows(label: str) -> dict[str, Any]:
    """Build one complete tenant graph: canvas, argument, areas, demand, cards."""
    org_id, user_id, project_id = uuid4(), uuid4(), uuid4()
    canvas_id, argument_id = uuid4(), uuid4()
    area_id, sub_area_id = uuid4(), uuid4()
    return {
        "label": label,
        "org_id": org_id,
        "user_id": user_id,
        "project_id": project_id,
        "canvas_id": canvas_id,
        "argument_id": argument_id,
        "area_id": area_id,
        "sub_area_id": sub_area_id,
        "area_name": f"{label} area",
        "sub_area_name": f"{label} sub-area",
        "product_line": f"{label} product line",
        "actor": AuthenticatedUser(
            user_id=user_id,
            issuer="https://test.identity.example",
            subject=f"sub-map-{user_id.hex[:8]}",
            email=f"map-{user_id.hex[:8]}@example.test",
            display_name=f"Map User {label}",
        ),
    }


async def _seed(session: AsyncSession, tenant: dict[str, Any]) -> None:
    label = tenant["label"]
    org_id = tenant["org_id"]
    project_id = tenant["project_id"]
    user_id = tenant["user_id"]
    canvas_id = tenant["canvas_id"]
    actor = tenant["actor"]

    session.add(Organization(id=org_id, name=f"Org {label}", slug=f"org-map-{org_id.hex[:8]}"))
    session.add(
        User(
            id=user_id,
            email=actor.email,
            normalized_email=actor.email,
            identity_issuer=actor.issuer,
            identity_subject=actor.subject,
            display_name=actor.display_name,
        )
    )
    await session.flush()

    session.add(
        OrganizationMember(
            organization_id=org_id,
            user_id=user_id,
            role_id=MEMBER_ROLE_ID,
            status="active",
            joined_at=datetime.now(UTC),
        )
    )
    await session.flush()

    session.add(
        Project(
            id=project_id,
            organization_id=org_id,
            name=f"Project {label}",
            slug=f"proj-map-{project_id.hex[:8]}",
        )
    )
    await session.flush()

    session.add(
        ProjectMember(
            organization_id=org_id,
            project_id=project_id,
            user_id=user_id,
            role_id=MEMBER_ROLE_ID,
        )
    )
    await session.flush()

    session.add(
        Canvas(
            id=canvas_id,
            organization_id=org_id,
            project_id=project_id,
            product_line=None,
        )
    )
    await session.flush()

    # A product-line child canvas, so the tree has a second level to leak.
    session.add(
        Canvas(
            id=uuid4(),
            organization_id=org_id,
            project_id=project_id,
            parent_id=canvas_id,
            product_line=tenant["product_line"],
        )
    )
    session.add(
        Argument(
            id=tenant["argument_id"],
            organization_id=org_id,
            project_id=project_id,
            canvas_id=canvas_id,
            order=0,
            differentiation_pillar=f"{label} pillar",
        )
    )
    await session.flush()

    session.add(
        Claim(
            id=uuid4(),
            organization_id=org_id,
            project_id=project_id,
            canvas_id=canvas_id,
            argument_id=tenant["argument_id"],
            row="pillar",
            text=f"{label} claim",
        )
    )
    session.add(
        Area(
            id=tenant["area_id"],
            organization_id=org_id,
            project_id=project_id,
            canvas_id=canvas_id,
            parent_id=None,
            name=tenant["area_name"],
            default_argument_id=tenant["argument_id"],
        )
    )
    await session.flush()

    session.add(
        Area(
            id=tenant["sub_area_id"],
            organization_id=org_id,
            project_id=project_id,
            canvas_id=canvas_id,
            parent_id=tenant["area_id"],
            name=tenant["sub_area_name"],
        )
    )
    await session.flush()

    session.add(
        DemandNode(
            id=uuid4(),
            organization_id=org_id,
            project_id=project_id,
            type="keyword",
            text=f"{label} kept keyword",
            area_id=tenant["sub_area_id"],
            status=DemandNodeStatus.KEPT,
            origin=DemandNodeOrigin.UPLOAD,
        )
    )
    session.add(
        ContentCard(
            id=uuid4(),
            organization_id=org_id,
            project_id=project_id,
            kind="cluster",
            area_id=tenant["sub_area_id"],
            state="live",
            origin="import",
            title=f"{label} imported page",
            url=f"https://{label.lower()}.example.test/page",
        )
    )
    await session.flush()


@pytest_asyncio.fixture
async def two_tenants() -> AsyncIterator[tuple[dict[str, Any], dict[str, Any]]]:
    """Seed two independent tenants as superuser, then clean both up."""
    tenant_a = _tenant_rows("Alpha")
    tenant_b = _tenant_rows("Bravo")

    setup_engine = create_async_engine(DATABASE_URL, echo=False)
    setup_factory = async_sessionmaker(setup_engine, expire_on_commit=False)
    async with setup_factory() as session:
        await _seed(session, tenant_a)
        await _seed(session, tenant_b)
        await session.commit()

    try:
        yield tenant_a, tenant_b
    finally:
        async with setup_factory() as session:
            for tenant in (tenant_a, tenant_b):
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
                await session.execute(
                    text("DELETE FROM organizations WHERE id = :o"), {"o": tenant["org_id"]}
                )
                await session.execute(
                    text("DELETE FROM users WHERE id = :u"), {"u": tenant["user_id"]}
                )
            await session.commit()
        await setup_engine.dispose()


def _collect(node: Any) -> tuple[set[UUID], set[str]]:
    """Every id and every name reachable anywhere in a returned map."""
    ids: set[UUID] = {node.id}
    names: set[str] = {node.name}

    def walk_areas(areas: list[Any]) -> None:
        for area in areas:
            ids.add(area.id)
            names.add(area.name)
            if area.default_argument_pillar:
                names.add(area.default_argument_pillar)
            walk_areas(area.children)

    def walk_canvases(canvas: Any) -> None:
        ids.add(canvas.id)
        names.add(canvas.name)
        walk_areas(canvas.areas)
        for child in canvas.product_lines:
            walk_canvases(child)

    walk_canvases(node)
    return ids, names


@pytest.mark.asyncio
async def test_strategy_map_never_returns_another_projects_graph(
    session_factory: async_sessionmaker[AsyncSession],
    two_tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    tenant_a, tenant_b = two_tenants

    async with session_factory() as session:
        result = await StrategyMapService(session).get_strategy_map(
            tenant_a["org_id"], tenant_a["project_id"], actor=tenant_a["actor"]
        )

    assert result.company_canvas is not None
    ids, names = _collect(result.company_canvas)

    # Project A's own graph is present.
    assert tenant_a["canvas_id"] in ids
    assert tenant_a["area_id"] in ids
    assert tenant_a["sub_area_id"] in ids
    assert tenant_a["area_name"] in names
    assert tenant_a["product_line"] in names

    # Nothing of project B's is reachable.
    assert tenant_b["canvas_id"] not in ids
    assert tenant_b["area_id"] not in ids
    assert tenant_b["sub_area_id"] not in ids
    assert tenant_b["area_name"] not in names
    assert tenant_b["sub_area_name"] not in names
    assert tenant_b["product_line"] not in names
    assert "Bravo pillar" not in names


@pytest.mark.asyncio
async def test_strategy_map_counts_exclude_another_projects_rows(
    session_factory: async_sessionmaker[AsyncSession],
    two_tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    """Aggregates must be scoped too — a leak here shows up as an inflated count."""
    tenant_a, _ = two_tenants

    async with session_factory() as session:
        result = await StrategyMapService(session).get_strategy_map(
            tenant_a["org_id"], tenant_a["project_id"], actor=tenant_a["actor"]
        )

    assert result.company_canvas is not None
    assert result.company_canvas.cell_count == 1  # only project A's single claim
    assert result.company_canvas.argument_count == 1

    sub_area = result.company_canvas.areas[0].children[0]
    assert sub_area.id == tenant_a["sub_area_id"]
    assert sub_area.demand_count == 1  # only project A's kept node
    assert sub_area.card_count == 1  # only project A's imported card
    assert result.unassigned_card_count == 0


@pytest.mark.asyncio
async def test_strategy_map_denies_a_project_the_actor_does_not_belong_to(
    session_factory: async_sessionmaker[AsyncSession],
    two_tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    """Project A's user asking for project B's map is refused, not served an empty tree."""
    tenant_a, tenant_b = two_tenants

    async with session_factory() as session:
        with pytest.raises((ResourceNotFound, PermissionDenied)):
            await StrategyMapService(session).get_strategy_map(
                tenant_b["org_id"], tenant_b["project_id"], actor=tenant_a["actor"]
            )


@pytest.mark.asyncio
async def test_strategy_map_denies_a_borrowed_project_id_under_the_actors_own_org(
    session_factory: async_sessionmaker[AsyncSession],
    two_tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    """Pairing your own organization with another tenant's project id is still refused."""
    tenant_a, tenant_b = two_tenants

    async with session_factory() as session:
        with pytest.raises((ResourceNotFound, PermissionDenied)):
            await StrategyMapService(session).get_strategy_map(
                tenant_a["org_id"], tenant_b["project_id"], actor=tenant_a["actor"]
            )
