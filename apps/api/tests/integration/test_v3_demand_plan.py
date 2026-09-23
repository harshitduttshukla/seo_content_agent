"""Live-database tests for the V3 Plan action (Strategy → Demand → ContentCard).

Seeds two full tenants, runs preview and confirm through DemandService as the
non-owner ``seo_content_app`` role, and reads the resulting rows back as the
owner. Covers read-only preview, atomic confirm, duplicate protection, config
use, tenant isolation, RBAC and the single action-level JobRun.
"""

import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from app.core.errors import PermissionDenied, ResourceNotFound
from app.domains.content_cards.models import ContentCard
from app.domains.content_cards.repository import ContentCardRepository
from app.domains.demand.models import DemandNode, DemandNodeOrigin
from app.domains.demand.service import DemandService
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.integration import test_v3_strategy_map_isolation as isolation

pytestmark = pytest.mark.integration

DATABASE_URL = isolation.DATABASE_URL
db_engine = isolation.db_engine
session_factory = isolation.session_factory

VIEWER_ROLE_ID = UUID("00000000-0000-0000-0000-000000000006")


async def _cleanup(session: AsyncSession, tenant: dict[str, Any]) -> None:
    await session.execute(
        text("DELETE FROM job_runs WHERE project_id = :p"), {"p": tenant["project_id"]}
    )
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


def _node(tenant: dict[str, Any], label: str, **fields: Any) -> DemandNode:
    values: dict[str, Any] = {
        "type": "keyword",
        "volume": 500,
        "country": "IN",
        "area_id": tenant["area_id"],
        "status": "kept",
        "score": 0.5,
        "origin": DemandNodeOrigin.UPLOAD,
    }
    values.update(fields)
    return DemandNode(
        id=uuid4(),
        organization_id=tenant["org_id"],
        project_id=tenant["project_id"],
        text=f"{tenant['label']} {label}",
        **values,
    )


@pytest_asyncio.fixture
async def owner_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(DATABASE_URL, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def tenants(
    owner_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[tuple[dict[str, Any], dict[str, Any]]]:
    """Two tenants, each with a configured workspace and a set of demand nodes."""
    alpha, bravo = isolation._tenant_rows("Alpha"), isolation._tenant_rows("Bravo")
    configs = {
        "Alpha": {
            "cluster_volume_floor": 300,
            "word_budgets": {"pillar": 2400, "cluster": 800, "compare": 1100},
            "markets": [{"lang": "en", "country": "IN"}],
        },
        # Bravo's floor would turn every Alpha node into a cluster if it leaked.
        "Bravo": {"cluster_volume_floor": 0, "word_budgets": {"pillar": 1}},
    }
    async with owner_factory() as session:
        for tenant in (alpha, bravo):
            await isolation._seed(session, tenant)
            await session.execute(
                text("UPDATE projects SET workspace_config = CAST(:c AS jsonb) WHERE id = :p"),
                {"c": json.dumps(configs[tenant["label"]]), "p": tenant["project_id"]},
            )
            nodes = {
                "top": _node(tenant, "top", score=0.9, volume=100),
                "cluster": _node(tenant, "cluster", score=0.6, volume=300),
                "secondary": _node(tenant, "secondary", score=0.7, volume=299),
                "compare": _node(
                    tenant, "compare", score=0.95, funnel="bofu", competitor_names=["Rival"]
                ),
                "us": _node(tenant, "us market", country="US", score=0.4),
                "discarded": _node(tenant, "discarded", status="discarded", score=1.0),
            }
            session.add_all(nodes.values())
            tenant["nodes"] = nodes
        await session.commit()
    try:
        yield alpha, bravo
    finally:
        async with owner_factory() as session:
            for tenant in (alpha, bravo):
                await _cleanup(session, tenant)
            await session.commit()


def _ids(tenant: dict[str, Any], *names: str) -> list[UUID]:
    return [tenant["nodes"][name].id for name in names]


ALL = ("top", "cluster", "secondary", "compare", "us", "discarded")


async def _plan_rows(factory: async_sessionmaker[AsyncSession], tenant: dict[str, Any]) -> Any:
    async with factory() as session:
        cards = (
            await session.execute(
                text(
                    "SELECT kind, title, state, origin, market, word_budget, area_id, "
                    "primary_demand_id, secondary_demand_ids FROM content_cards "
                    "WHERE project_id = :p AND origin = 'plan' ORDER BY kind, title"
                ),
                {"p": tenant["project_id"]},
            )
        ).all()
        runs = (
            await session.execute(
                text(
                    "SELECT job_type, triggered_by, model, provider, total_tokens, "
                    "estimated_cost_usd FROM job_runs WHERE project_id = :p"
                ),
                {"p": tenant["project_id"]},
            )
        ).all()
    return cards, runs


@pytest.mark.asyncio
async def test_preview_reports_the_plan_and_writes_nothing(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = tenants
    async with session_factory() as session:
        preview = await DemandService(session).preview_plan(
            alpha["org_id"], alpha["project_id"], _ids(alpha, *ALL), actor=alpha["actor"]
        )

    assert (preview.selected_count, preview.eligible_count, preview.skipped_count) == (6, 5, 1)
    assert preview.skipped[0].reason == "Status is discarded; only kept nodes are planned."
    groups = {(g.area_name, g.market_country): g for g in preview.groups}
    india = groups[(alpha["area_name"], "IN")]
    assert india.counts.model_dump() == {
        "pillar": 1,
        "cluster": 1,
        "compare": 1,
        "refresh": 0,
        "secondary_demands": 1,
    }
    # Compare precedence: the 0.95 BOFU node is compare; 0.9 is pillar.
    by_kind = {card.kind: card for card in india.cards}
    assert by_kind["compare"].primary_text == "Alpha compare"
    assert by_kind["pillar"].primary_text == "Alpha top"
    assert [s.text for s in by_kind["pillar"].secondary_demands] == ["Alpha secondary"]
    assert groups[(alpha["area_name"], "US")].counts.pillar == 1
    assert len(preview.deferred) == 2

    cards, runs = await _plan_rows(owner_factory, alpha)
    assert cards == [] and runs == []


@pytest.mark.asyncio
async def test_confirm_creates_planned_cards_from_config_and_one_ui_job_run(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = tenants

    def no_model(*_: Any, **__: Any) -> None:
        raise AssertionError("Plan must not obtain an AI provider")

    with patch("app.domains.ai.service.get_ai_provider", no_model):
        async with session_factory() as session:
            result = await DemandService(session).confirm_plan(
                alpha["org_id"], alpha["project_id"], _ids(alpha, *ALL), actor=alpha["actor"]
            )

    assert result.created_count == 4
    cards, runs = await _plan_rows(owner_factory, alpha)
    summary = [(c.kind, c.title, c.state, c.origin, c.market, c.word_budget) for c in cards]
    assert summary == [
        ("cluster", "Alpha cluster", "planned", "plan", {"country": "IN", "lang": "en"}, 800),
        ("compare", "Alpha compare", "planned", "plan", {"country": "IN", "lang": "en"}, 1100),
        ("pillar", "Alpha top", "planned", "plan", {"country": "IN", "lang": "en"}, 2400),
        ("pillar", "Alpha us market", "planned", "plan", {"country": "US"}, 2400),
    ]
    pillar = next(c for c in cards if c.title == "Alpha top")
    assert pillar.primary_demand_id == alpha["nodes"]["top"].id
    assert pillar.secondary_demand_ids == [str(alpha["nodes"]["secondary"].id)]
    assert {c.area_id for c in cards} == {alpha["area_id"]}

    # Exactly one action-level run: no model, no provider, no tokens, no cost.
    assert runs == [("demand_plan", "ui", "deterministic", "internal", 0, 0.0)]


@pytest.mark.asyncio
async def test_confirming_again_skips_every_node_already_carded(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = tenants
    selection = _ids(alpha, "top", "cluster", "secondary", "compare")
    async with session_factory() as session:
        await DemandService(session).confirm_plan(
            alpha["org_id"], alpha["project_id"], selection, actor=alpha["actor"]
        )
    async with session_factory() as session:
        again = await DemandService(session).preview_plan(
            alpha["org_id"], alpha["project_id"], selection, actor=alpha["actor"]
        )

    # The secondary is carded through the pillar's secondary_demand_ids.
    assert again.eligible_count == 0
    assert {s.reason for s in again.skipped} == {"DemandNode already has ContentCard."}
    assert len(again.skipped) == 4


@pytest.mark.asyncio
async def test_existing_imported_card_on_the_node_blocks_a_duplicate(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = tenants
    async with owner_factory() as session:
        await session.execute(
            text("UPDATE content_cards SET primary_demand_id = :n WHERE project_id = :p"),
            {"n": alpha["nodes"]["top"].id, "p": alpha["project_id"]},
        )
        await session.commit()
    async with session_factory() as session:
        preview = await DemandService(session).preview_plan(
            alpha["org_id"], alpha["project_id"], _ids(alpha, "top"), actor=alpha["actor"]
        )
    assert preview.groups == []
    assert preview.skipped[0].reason == "DemandNode already has ContentCard."


@pytest.mark.asyncio
async def test_failure_midway_rolls_back_every_card_and_the_job_run(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = tenants
    original = ContentCardRepository.add_content_card
    calls = {"count": 0}

    def fail_on_third(self: ContentCardRepository, entity: ContentCard) -> None:
        calls["count"] += 1
        if calls["count"] == 3:
            raise RuntimeError("simulated write failure")
        original(self, entity)

    with patch.object(ContentCardRepository, "add_content_card", fail_on_third):
        async with session_factory() as session:
            with pytest.raises(RuntimeError, match="simulated write failure"):
                await DemandService(session).confirm_plan(
                    alpha["org_id"], alpha["project_id"], _ids(alpha, *ALL), actor=alpha["actor"]
                )

    assert calls["count"] == 3
    cards, runs = await _plan_rows(owner_factory, alpha)
    assert cards == [] and runs == []


@pytest.mark.asyncio
async def test_plan_never_reads_or_writes_another_projects_rows(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, bravo = tenants
    # Alpha selects its own nodes plus every Bravo node id.
    selection = _ids(alpha, "top", "cluster", "secondary") + _ids(bravo, *ALL)
    async with session_factory() as session:
        result = await DemandService(session).confirm_plan(
            alpha["org_id"], alpha["project_id"], selection, actor=alpha["actor"]
        )

    bravo_ids = set(_ids(bravo, *ALL))
    assert {s.node_id for s in result.skipped} == bravo_ids
    assert {s.reason for s in result.skipped} == {"Not found in this project."}
    assert all(s.text is None for s in result.skipped)  # no Bravo text leaks back
    # Alpha's own floor (300) and budgets applied, not Bravo's (0, pillar 1).
    alpha_cards, _ = await _plan_rows(owner_factory, alpha)
    assert [(c.kind, c.word_budget) for c in alpha_cards] == [("cluster", 800), ("pillar", 2400)]
    bravo_cards, bravo_runs = await _plan_rows(owner_factory, bravo)
    assert bravo_cards == [] and bravo_runs == []


@pytest.mark.asyncio
async def test_plan_is_refused_for_another_tenants_project(
    session_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, bravo = tenants
    for organization_id in (bravo["org_id"], alpha["org_id"]):
        async with session_factory() as session:
            with pytest.raises((ResourceNotFound, PermissionDenied)):
                await DemandService(session).preview_plan(
                    organization_id, bravo["project_id"], _ids(bravo, "top"), actor=alpha["actor"]
                )
        async with session_factory() as session:
            with pytest.raises((ResourceNotFound, PermissionDenied)):
                await DemandService(session).confirm_plan(
                    organization_id, bravo["project_id"], _ids(bravo, "top"), actor=alpha["actor"]
                )


@pytest.mark.asyncio
async def test_a_viewer_can_preview_but_cannot_confirm(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = tenants
    async with owner_factory() as session:
        for table in ("organization_members", "project_members"):
            await session.execute(
                text(f"UPDATE {table} SET role_id = :r WHERE user_id = :u"),
                {"r": VIEWER_ROLE_ID, "u": alpha["user_id"]},
            )
        await session.commit()

    async with session_factory() as session:
        preview = await DemandService(session).preview_plan(
            alpha["org_id"], alpha["project_id"], _ids(alpha, "top"), actor=alpha["actor"]
        )
    assert preview.eligible_count == 1
    async with session_factory() as session:
        with pytest.raises(PermissionDenied):
            await DemandService(session).confirm_plan(
                alpha["org_id"], alpha["project_id"], _ids(alpha, "top"), actor=alpha["actor"]
            )
    cards, runs = await _plan_rows(owner_factory, alpha)
    assert cards == [] and runs == []


@pytest.mark.asyncio
async def test_database_rejection_after_earlier_inserts_leaves_zero_cards(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    tenants: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    """The third card breaks a CHECK constraint at flush, after two rows were sent."""
    alpha, _ = tenants
    original = ContentCardRepository.add_content_card
    calls = {"count": 0}

    def corrupt_third(self: ContentCardRepository, entity: ContentCard) -> None:
        calls["count"] += 1
        if calls["count"] == 3:
            entity.kind = "not-a-kind"  # violates ck_content_cards_kind_allowed
        original(self, entity)

    with patch.object(ContentCardRepository, "add_content_card", corrupt_third):
        async with session_factory() as session:
            with pytest.raises(IntegrityError):
                await DemandService(session).confirm_plan(
                    alpha["org_id"], alpha["project_id"], _ids(alpha, *ALL), actor=alpha["actor"]
                )

    cards, runs = await _plan_rows(owner_factory, alpha)
    assert cards == [] and runs == []
