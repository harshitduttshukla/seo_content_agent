"""Live-database tests for V3 card detail and the Bundle → Outline workflow.

Runs as the non-owner ``seo_content_app`` role so RLS is enforced. Each tenant
gets an argument with approved, superseded and unapproved claims, keyword and
prompt demand, a social proof, and a stored crawl page; a planned card cites
them. AI calls use a scripted test double, never a paid provider.
"""

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from app.core.errors import ConflictError, DomainError, PermissionDenied, ResourceNotFound
from app.domains.brand_kit.models import BrandKit, SocialProof
from app.domains.canvas.models import Claim
from app.domains.canvas.repository import CanvasRepository
from app.domains.canvas.schemas import ClaimCitationCreateRequest
from app.domains.canvas.service import CanvasService
from app.domains.content.models import ContentPage
from app.domains.content_cards.models import ContentCard, ContentCardClaim
from app.domains.content_cards.outline import OutlineV3
from app.domains.content_cards.workflow_schemas import (
    BundleBuildRequest,
    OutlineGenerateRequest,
    OutlineSaveRequest,
)
from app.domains.content_cards.workflow_service import CardWorkflowService
from app.domains.content_harness.schemas import V3OutlineHarnessInput
from app.domains.content_harness.service import ContentHarnessService
from app.domains.demand.models import DemandNode, DemandNodeOrigin, DemandNodeStatus
from app.domains.job_runs.models import JobRun
from app.domains.websites.models import Website
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.integration import test_v3_plan_lock as lock_tests
from tests.integration import test_v3_strategy_map_isolation as isolation
from tests.unit.test_v3_outline_contract import ScriptedProvider

pytestmark = pytest.mark.integration

DATABASE_URL = isolation.DATABASE_URL
db_engine = isolation.db_engine
session_factory = isolation.session_factory
owner_factory = lock_tests.owner_factory


async def _seed_workflow(session: AsyncSession, tenant: dict[str, Any]) -> None:
    org, project, label = tenant["org_id"], tenant["project_id"], tenant["label"]
    scope = {"organization_id": org, "project_id": project}
    ids = {k: uuid4() for k in ("approved", "old", "draft", "demand", "prompt", "site", "page")}
    tenant.update({f"{k}_id": v for k, v in ids.items()})
    session.add_all(
        [
            Claim(id=ids["approved"], **scope, canvas_id=tenant["canvas_id"],
                  argument_id=tenant["argument_id"], row="pillar",
                  text=f"{label} files IOSS returns", approved=True, version=2),
            Claim(id=ids["old"], **scope, canvas_id=tenant["canvas_id"],
                  argument_id=tenant["argument_id"], row="pillar", text=f"{label} old claim",
                  approved=True, superseded_by=ids["approved"]),
            Claim(id=ids["draft"], **scope, canvas_id=tenant["canvas_id"],
                  argument_id=tenant["argument_id"], row="pillar", text=f"{label} unapproved"),
            DemandNode(id=ids["demand"], **scope, type="keyword", text=f"{label} landed cost",
                       volume=390, status=DemandNodeStatus.KEPT, origin=DemandNodeOrigin.UPLOAD),
            DemandNode(id=ids["prompt"], **scope, type="prompt", text=f"who pays {label} duties",
                       status=DemandNodeStatus.KEPT, origin=DemandNodeOrigin.UPLOAD,
                       citation_gap=1.0, platforms=["chatgpt"]),
            BrandKit(id=uuid4(), **scope, banned_words=["cheap"], tone_profile="plain"),
            SocialProof(id=uuid4(), **scope, label=f"{label} proof", proof_type="logo",
                        approved=True),
            Website(id=ids["site"], **scope, name=label, base_url=f"https://{label}.test",
                    normalized_host=f"{label.lower()}.test"),
        ]
    )  # fmt: skip
    await session.flush()
    tenant["page_url"] = f"https://{label.lower()}.test/landed-cost"
    session.add(
        ContentPage(
            id=ids["page"], **scope, website_id=ids["site"], url=tenant["page_url"],
            normalized_url=tenant["page_url"], title=f"{label} landed cost guide",
            cleaned_content="Landed cost is duty plus tax.",
        )
    )  # fmt: skip
    card_id = uuid4()
    tenant["card_id"] = card_id
    session.add(
        ContentCard(
            id=card_id, **scope, kind="pillar", state="planned", origin="plan",
            title=f"{label} landed cost", argument_id=tenant["argument_id"],
            area_id=tenant["area_id"], primary_demand_id=ids["demand"],
            secondary_demand_ids=[str(ids["prompt"])], market={"lang": "en", "country": "GB"},
        )
    )  # fmt: skip


@pytest_asyncio.fixture
async def pair(
    owner_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[tuple[dict[str, Any], dict[str, Any]]]:
    alpha, bravo = isolation._tenant_rows("Alpha"), isolation._tenant_rows("Bravo")
    async with owner_factory() as session:
        for tenant in (alpha, bravo):
            await isolation._seed(session, tenant)
            await _seed_workflow(session, tenant)
        await session.commit()
    try:
        yield alpha, bravo
    finally:
        async with owner_factory() as session:
            for tenant in (alpha, bravo):
                params = {"p": tenant["project_id"], "o": tenant["org_id"]}
                for statement in (
                    "DELETE FROM audit_logs WHERE project_id = :p",
                    "DELETE FROM content_harness_runs WHERE project_id = :p",
                    "DELETE FROM job_runs WHERE project_id = :p",
                    "DELETE FROM content_cards WHERE project_id = :p",
                    "DELETE FROM content_pages WHERE project_id = :p",
                    "DELETE FROM websites WHERE project_id = :p",
                    "DELETE FROM social_proofs WHERE project_id = :p",
                    "DELETE FROM brand_kits WHERE project_id = :p",
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


def _service(session: AsyncSession, *texts: str) -> CardWorkflowService:
    return CardWorkflowService(session, provider=ScriptedProvider(*texts))


async def _detail(factory: async_sessionmaker[AsyncSession], t: dict[str, Any], **kw: Any) -> Any:
    async with factory() as session:
        return await _service(session).get_detail(
            kw.get("org", t["org_id"]), kw.get("project", t["project_id"]),
            kw.get("card", t["card_id"]), actor=kw.get("actor", t["actor"]),
        )  # fmt: skip


async def _bundle(factory: async_sessionmaker[AsyncSession], t: dict[str, Any], rev: int) -> Any:
    async with factory() as session:
        return await _service(session).build_bundle(
            t["org_id"], t["project_id"], t["card_id"], BundleBuildRequest(revision=rev),
            actor=t["actor"], request_id="test-bundle",
        )  # fmt: skip


async def _generate(
    factory: async_sessionmaker[AsyncSession], t: dict[str, Any], *texts: str
) -> Any:
    async with factory() as session:
        return await _service(session, *texts).generate_outline(
            t["org_id"], t["project_id"], t["card_id"], OutlineGenerateRequest(), actor=t["actor"]
        )


async def _save(
    factory: async_sessionmaker[AsyncSession], t: dict[str, Any], outline: Any, rev: int
) -> Any:
    async with factory() as session:
        return await _service(session).save_outline(
            t["org_id"], t["project_id"], t["card_id"],
            OutlineSaveRequest(outline=OutlineV3.model_validate(outline), revision=rev),
            actor=t["actor"], request_id="test-save",
        )  # fmt: skip


async def _card(factory: async_sessionmaker[AsyncSession], card_id: UUID) -> ContentCard:
    async with factory() as session:
        card = await session.scalar(select(ContentCard).where(ContentCard.id == card_id))
        assert card is not None
        return card


def outline_for(t: dict[str, Any], **section: Any) -> dict[str, Any]:
    return {
        "primary_mode": "keyword",
        "title": "Landed cost",
        "sections": [
            {
                "section_id": "s1",
                "order": 1,
                "heading": "What landed cost includes",
                "claim_ids": [str(t["approved_id"])],
                "target_demand_id": str(t["demand_id"]),
                "planned_internal_links": [{"page_id": str(t["page_id"]), "url": t["page_url"]}],
                **section,
            }
        ],
    }


# ── Detail ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detail_shows_real_card_context_and_only_current_approved_claims(
    session_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    detail = await _detail(session_factory, alpha)

    assert detail.card.id == alpha["card_id"] and detail.card.state == "planned"
    assert detail.outline is None and detail.bundle is None
    context = detail.context
    assert [c.id for c in context.claims] == [alpha["approved_id"]]  # not superseded/unapproved
    assert {(d.id, d.role) for d in context.demand} == {
        (alpha["demand_id"], "primary"),
        (alpha["prompt_id"], "secondary"),
    }
    assert context.rules.brand.words_to_avoid == ["cheap"]
    assert context.tone.social_proof == ["Alpha proof"]
    assert context.card.market == "en-GB" and context.card.primary_mode == "keyword"
    assert [p.url for p in context.references.existing_pages.pages] == [alpha["page_url"]]
    assert context.references.website.crawled_pages[0].content_snippet
    assert context.pitch.differentiation_pillar == "Alpha pillar"
    kinds = {(s.section, s.source_type) for s in context.sources}
    assert {("claims", "claim"), ("demand", "demand_node"), ("rules", "brand_kit"),
            ("references", "content_page"), ("tone", "social_proof")} <= kinds  # fmt: skip
    assert [o.id for o in detail.claim_options] == [alpha["approved_id"]]
    assert detail.actions.can_build_bundle and not detail.actions.can_generate_outline
    assert {c.key: c.status for c in detail.checks}["bundle_exists"] == "fail"


@pytest.mark.asyncio
async def test_detail_is_tenant_and_project_isolated(
    session_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, bravo = pair
    with pytest.raises(ResourceNotFound):  # bravo's card through alpha's scope
        await _detail(session_factory, alpha, card=bravo["card_id"])
    with pytest.raises((ResourceNotFound, PermissionDenied)):  # bravo's scope, alpha's identity
        await _detail(session_factory, bravo, actor=alpha["actor"])
    with pytest.raises(ResourceNotFound):
        await _detail(session_factory, alpha, card=uuid4())
    detail = await _detail(session_factory, alpha)
    assert all("Bravo" not in c.text for c in detail.context.claims)


@pytest.mark.asyncio
async def test_viewer_reads_detail_but_cannot_bundle_generate_or_save(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    await lock_tests._set_role(owner_factory, alpha, lock_tests.VIEWER_ROLE_ID)
    assert (await _detail(session_factory, alpha)).card.id == alpha["card_id"]
    with pytest.raises(PermissionDenied):
        await _bundle(session_factory, alpha, 1)
    with pytest.raises(PermissionDenied):
        await _generate(session_factory, alpha, "{}")
    with pytest.raises(PermissionDenied):
        await _save(session_factory, alpha, outline_for(alpha), 1)
    assert (await _card(owner_factory, alpha["card_id"])).state == "planned"


# ── Bundle ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bundle_moves_planned_to_bundled_stores_a_job_run_and_is_reused(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    first = await _bundle(session_factory, alpha, 1)
    assert (first.card.state, first.card.revision, first.reused) == ("bundled", 2, False)
    card = await _card(owner_factory, alpha["card_id"])
    assert card.bundle_ref == first.bundle.bundle_ref
    async with owner_factory() as session:
        run = await session.get(JobRun, first.bundle.bundle_ref)
        assert run is not None and run.job_type == "v3_context_bundle"
        assert run.output_data is not None
        assert run.output_data["content_hash"] == first.bundle.content_hash
        assert run.entity_id == alpha["card_id"] and run.triggered_by == str(alpha["user_id"])

    again = await _bundle(session_factory, alpha, 2)
    assert again.reused and again.bundle.bundle_ref == first.bundle.bundle_ref
    assert again.card.revision == 2  # nothing changed, nothing bumped

    async with owner_factory() as session:  # a source changes → the bundle is stale
        await session.execute(
            text("UPDATE claims SET text = 'Alpha files IOSS returns monthly' WHERE id = :c"),
            {"c": alpha["approved_id"]},
        )
        await session.commit()
    detail = await _detail(session_factory, alpha)
    assert detail.bundle is not None and not detail.bundle.is_current
    rebuilt = await _bundle(session_factory, alpha, 2)
    assert not rebuilt.reused and rebuilt.bundle.bundle_ref != first.bundle.bundle_ref
    assert rebuilt.card.state == "bundled" and rebuilt.card.revision == 3


@pytest.mark.asyncio
async def test_bundle_revision_conflict_and_wrong_state(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    with pytest.raises(ConflictError) as raised:
        await _bundle(session_factory, alpha, 7)
    assert raised.value.code == "VERSION_CONFLICT"
    async with owner_factory() as session:
        await session.execute(
            text("UPDATE content_cards SET state = 'backlog' WHERE id = :c"),
            {"c": alpha["card_id"]},
        )
        await session.commit()
    with pytest.raises(ConflictError) as raised:
        await _bundle(session_factory, alpha, 1)
    assert raised.value.code == "BUNDLE_NOT_ALLOWED"


# ── Generate ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_requires_a_current_bundle(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    with pytest.raises(ConflictError) as raised:
        await _generate(session_factory, alpha, json.dumps(outline_for(alpha)))
    assert raised.value.code == "BUNDLE_REQUIRED"
    await _bundle(session_factory, alpha, 1)
    async with owner_factory() as session:
        await session.execute(
            text("UPDATE demand_nodes SET volume = 999 WHERE id = :d"), {"d": alpha["demand_id"]}
        )
        await session.commit()
    with pytest.raises(ConflictError) as raised:
        await _generate(session_factory, alpha, json.dumps(outline_for(alpha)))
    assert raised.value.code == "BUNDLE_STALE"


@pytest.mark.asyncio
async def test_generate_returns_a_proposal_and_records_the_job_without_touching_the_card(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    built = await _bundle(session_factory, alpha, 1)
    proposal = await _generate(session_factory, alpha, json.dumps(outline_for(alpha)))

    assert proposal.prompt_version == "v3.outline.v1" and proposal.attempts == 1
    assert proposal.bundle_ref == built.bundle.bundle_ref
    card = await _card(owner_factory, alpha["card_id"])
    assert (card.outline, card.state, card.revision) == (None, "bundled", 2)
    async with owner_factory() as session:
        run = await session.get(JobRun, proposal.job_run_id)
        assert run is not None and run.job_type == "v3_outline_generation"
        assert (run.status, run.provider, run.model) == ("completed", "scripted", "scripted-1")
        assert run.prompt_version == "v3.outline.v1" and run.total_tokens == 150
        assert run.input_data is not None
        assert run.input_data["bundle_hash"] == built.bundle.content_hash


@pytest.mark.asyncio
async def test_invalid_generation_is_rejected_after_one_retry_and_saves_nothing(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, bravo = pair
    await _bundle(session_factory, alpha, 1)
    foreign = json.dumps(outline_for(alpha, claim_ids=[str(bravo["approved_id"])]))
    with pytest.raises(DomainError) as raised:
        await _generate(session_factory, alpha, "not json", foreign)
    assert raised.value.code == "OUTLINE_INVALID"
    card = await _card(owner_factory, alpha["card_id"])
    assert (card.outline, card.state) == (None, "bundled")
    async with owner_factory() as session:
        run = await session.scalar(
            select(JobRun).where(
                JobRun.project_id == alpha["project_id"],
                JobRun.job_type == "v3_outline_generation",
            )
        )
        assert run is not None and run.status == "failed" and run.output_data is not None
        assert len(run.output_data["attempts"]) == 2  # type: ignore[arg-type]


# ── Save ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_moves_bundled_to_outlined_and_later_saves_keep_outlined(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    await _bundle(session_factory, alpha, 1)
    saved = await _save(session_factory, alpha, outline_for(alpha), 2)
    assert (saved.card.state, saved.card.revision) == ("outlined", 3)
    card = await _card(owner_factory, alpha["card_id"])
    assert card.outline is not None and card.outline["sections"][0]["heading"]  # type: ignore[index]

    edited = await _save(session_factory, alpha, outline_for(alpha, heading="Renamed"), 3)
    assert (edited.card.state, edited.card.revision) == ("outlined", 4)
    detail = await _detail(session_factory, alpha)
    assert detail.outline is not None and detail.outline.sections[0].heading == "Renamed"
    checks = {c.key: c.status for c in detail.checks}
    assert (
        checks["claims_resolve"] == checks["links_resolve"] == checks["demand_resolves"] == "pass"
    )


@pytest.mark.asyncio
async def test_save_revision_conflict_does_not_overwrite(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    await _bundle(session_factory, alpha, 1)
    with pytest.raises(ConflictError) as raised:
        await _save(session_factory, alpha, outline_for(alpha), 1)
    assert raised.value.code == "VERSION_CONFLICT"
    card = await _card(owner_factory, alpha["card_id"])
    assert (card.outline, card.state) == (None, "bundled")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("claim_ids", "UNKNOWN_CLAIM"),
        ("target_demand_id", "UNKNOWN_DEMAND"),
        ("planned_internal_links", "UNKNOWN_PAGE"),
        ("wrong_url", "URL_MISMATCH"),
        ("unapproved", "UNKNOWN_CLAIM"),
    ],
)
async def test_save_rejects_foreign_or_invented_references_and_keeps_state(
    field: str,
    code: str,
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, bravo = pair
    await _bundle(session_factory, alpha, 1)
    overrides: dict[str, Any] = {
        "claim_ids": {"claim_ids": [str(bravo["approved_id"])]},
        "target_demand_id": {"target_demand_id": str(bravo["demand_id"])},
        "planned_internal_links": {
            "planned_internal_links": [{"page_id": str(bravo["page_id"]), "url": bravo["page_url"]}]
        },
        "wrong_url": {
            "planned_internal_links": [{"page_id": str(alpha["page_id"]), "url": "https://x.test"}]
        },
        "unapproved": {"claim_ids": [str(alpha["draft_id"])]},
    }[field]
    with pytest.raises(DomainError) as raised:
        await _save(session_factory, alpha, outline_for(alpha, **overrides), 2)
    assert raised.value.code == "OUTLINE_INVALID"
    assert code in {i["code"] for i in raised.value.details["issues"]}  # type: ignore[index, union-attr]
    card = await _card(owner_factory, alpha["card_id"])
    assert (card.outline, card.state, card.revision) == (None, "bundled", 2)


@pytest.mark.asyncio
async def test_save_refused_before_bundling(
    session_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    with pytest.raises(ConflictError) as raised:
        await _save(session_factory, alpha, outline_for(alpha), 1)
    assert raised.value.code == "OUTLINE_NOT_ALLOWED"


# ── Harness ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_harness_runs_the_production_contract_on_the_card(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    built = await _bundle(session_factory, alpha, 1)
    provider = ScriptedProvider(json.dumps(outline_for(alpha)))
    async with session_factory() as session:
        run = await ContentHarnessService(provider=provider).run_v3_outline(
            session,
            actor=alpha["actor"],
            input_data=V3OutlineHarnessInput(
                project_id=alpha["project_id"], card_id=alpha["card_id"]
            ),
        )
        await session.commit()

    assert run.prompt_version == "v3.outline.v1" and run.provider == "scripted"
    assert run.context_data["bundle_hash"] == built.bundle.content_hash  # same bundle as production
    assert provider.requests[0].metadata["prompt_version"] == "v3.outline.v1"
    assert run.output_data["outline"] is not None
    assert run.evaluation_data["status"] == "PASS"
    card = await _card(owner_factory, alpha["card_id"])
    assert (card.outline, card.state) == (None, "bundled")  # the Harness never edits cards


# ── ContentCardClaim projection (additive; Strategy citations survive) ──


async def _links(factory: async_sessionmaker[AsyncSession], card_id: UUID) -> list[UUID]:
    async with factory() as session:
        rows = await session.scalars(
            select(ContentCardClaim.claim_id).where(ContentCardClaim.content_card_id == card_id)
        )
        return sorted(rows, key=str)


async def _second_claim(factory: async_sessionmaker[AsyncSession], t: dict[str, Any]) -> UUID:
    claim_id = uuid4()
    async with factory() as session:
        session.add(
            Claim(id=claim_id, organization_id=t["org_id"], project_id=t["project_id"],
                  canvas_id=t["canvas_id"], argument_id=t["argument_id"], row="pillar",
                  text=f"{t['label']} second claim", approved=True)
        )  # fmt: skip
        await session.commit()
    return claim_id


async def _strategy_cite(
    factory: async_sessionmaker[AsyncSession], t: dict[str, Any], claim_id: UUID
) -> None:
    """Cite ``claim_id`` on the card manually, through Strategy's own service."""
    async with factory() as session:
        await CanvasService(session).add_citation(
            t["org_id"], t["project_id"], claim_id,
            ClaimCitationCreateRequest(content_card_id=t["card_id"]), actor=t["actor"],
        )  # fmt: skip


async def _strategy_counts(
    factory: async_sessionmaker[AsyncSession], t: dict[str, Any], claim_ids: list[UUID]
) -> dict[UUID, int]:
    """Strategy's own citation counter, unchanged."""
    async with factory() as session:
        return await CanvasRepository(session).get_citation_counts_for_claims(
            t["org_id"], t["project_id"], claim_ids
        )


def _multi(t: dict[str, Any], *claim_sets: list[UUID]) -> dict[str, Any]:
    outline = outline_for(t)
    template = outline["sections"][0]
    outline["sections"] = [
        {**template, "section_id": f"s{i}", "order": i, "claim_ids": [str(c) for c in claims]}
        for i, claims in enumerate(claim_sets, start=1)
    ]
    return outline


@pytest.mark.asyncio
async def test_first_save_creates_card_claim_rows_without_duplicates(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    second = await _second_claim(owner_factory, alpha)
    await _bundle(session_factory, alpha, 1)
    approved = alpha["approved_id"]
    # The same claim in two sections, and twice in one section.
    await _save(session_factory, alpha, _multi(alpha, [approved, approved], [approved, second]), 2)

    assert await _links(owner_factory, alpha["card_id"]) == sorted([approved, second], key=str)
    assert await _strategy_counts(owner_factory, alpha, [approved, second]) == {
        approved: 1,
        second: 1,
    }


@pytest.mark.asyncio
async def test_editing_the_outline_adds_but_never_removes_card_claim_rows(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    second = await _second_claim(owner_factory, alpha)
    approved = alpha["approved_id"]
    await _bundle(session_factory, alpha, 1)
    await _save(session_factory, alpha, _multi(alpha, [approved]), 2)
    await _save(session_factory, alpha, _multi(alpha, [second]), 3)
    assert await _links(owner_factory, alpha["card_id"]) == sorted([approved, second], key=str)
    await _save(session_factory, alpha, _multi(alpha, []), 4)
    assert await _links(owner_factory, alpha["card_id"]) == sorted([approved, second], key=str)


@pytest.mark.asyncio
async def test_manual_strategy_citation_survives_outline_save(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    manual = await _second_claim(owner_factory, alpha)
    await _strategy_cite(owner_factory, alpha, manual)
    await _bundle(session_factory, alpha, 1)

    # The outline does not reference the manual claim; it adds its own.
    await _save(session_factory, alpha, _multi(alpha, [alpha["approved_id"]]), 2)
    assert await _links(owner_factory, alpha["card_id"]) == sorted(
        [alpha["approved_id"], manual], key=str
    )


@pytest.mark.asyncio
async def test_outline_claim_creates_missing_card_claim_row(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    await _bundle(session_factory, alpha, 1)
    assert await _links(owner_factory, alpha["card_id"]) == []
    await _save(session_factory, alpha, _multi(alpha, [alpha["approved_id"]]), 2)
    assert await _links(owner_factory, alpha["card_id"]) == [alpha["approved_id"]]


@pytest.mark.asyncio
async def test_claim_in_strategy_and_outline_stays_one_row(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    approved = alpha["approved_id"]
    await _strategy_cite(owner_factory, alpha, approved)
    await _bundle(session_factory, alpha, 1)
    await _save(session_factory, alpha, _multi(alpha, [approved], [approved]), 2)
    await _strategy_cite(owner_factory, alpha, approved)  # Strategy re-cite is a no-op too
    assert await _links(owner_factory, alpha["card_id"]) == [approved]
    assert await _strategy_counts(owner_factory, alpha, [approved]) == {approved: 1}


@pytest.mark.asyncio
async def test_removing_claim_from_outline_keeps_manual_strategy_citation(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    approved = alpha["approved_id"]
    await _strategy_cite(owner_factory, alpha, approved)
    await _bundle(session_factory, alpha, 1)
    await _save(session_factory, alpha, _multi(alpha, [approved]), 2)
    await _save(session_factory, alpha, _multi(alpha, []), 3)  # claim dropped from outline
    assert await _links(owner_factory, alpha["card_id"]) == [approved]
    assert await _strategy_counts(owner_factory, alpha, [approved]) == {approved: 1}


@pytest.mark.asyncio
async def test_save_leaves_other_cards_citations_and_strategy_counts_intact(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, bravo = pair
    approved = alpha["approved_id"]
    other_card = uuid4()
    async with owner_factory() as session:  # a citation made in Strategy on another card
        session.add(
            ContentCard(id=other_card, organization_id=alpha["org_id"],
                        project_id=alpha["project_id"], kind="cluster", state="live",
                        origin="manual", title="Alpha live page")
        )  # fmt: skip
        await session.flush()
        session.add(
            ContentCardClaim(id=uuid4(), organization_id=alpha["org_id"],
                             project_id=alpha["project_id"], content_card_id=other_card,
                             claim_id=approved)
        )  # fmt: skip
        await session.commit()
    await _bundle(session_factory, alpha, 1)

    await _save(session_factory, alpha, _multi(alpha, [approved]), 2)
    assert await _strategy_counts(owner_factory, alpha, [approved]) == {approved: 2}
    await _save(session_factory, alpha, _multi(alpha, []), 3)
    assert await _strategy_counts(owner_factory, alpha, [approved]) == {approved: 2}
    assert await _links(owner_factory, other_card) == [approved]
    assert await _strategy_counts(owner_factory, bravo, [bravo["approved_id"]]) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["foreign", "unapproved", "superseded"])
async def test_rejected_claims_write_no_card_claim_rows(
    bad: str,
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, bravo = pair
    await _bundle(session_factory, alpha, 1)
    await _save(session_factory, alpha, _multi(alpha, [alpha["approved_id"]]), 2)
    bad_id = {"foreign": bravo["approved_id"], "unapproved": alpha["draft_id"],
              "superseded": alpha["old_id"]}[bad]  # fmt: skip

    # A valid claim beside the bad one: nothing at all may be written.
    with pytest.raises(DomainError) as raised:
        await _save(session_factory, alpha, _multi(alpha, [], [bad_id]), 3)
    assert raised.value.code == "OUTLINE_INVALID"
    assert await _links(owner_factory, alpha["card_id"]) == [alpha["approved_id"]]
    assert await _links(owner_factory, bravo["card_id"]) == []
    card = await _card(owner_factory, alpha["card_id"])
    assert card.revision == 3 and card.outline is not None
    assert card.outline["sections"][0]["claim_ids"] == [str(alpha["approved_id"])]  # type: ignore[index]


@pytest.mark.asyncio
async def test_revision_conflict_leaves_card_claim_rows_untouched(
    session_factory: async_sessionmaker[AsyncSession],
    owner_factory: async_sessionmaker[AsyncSession],
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    alpha, _ = pair
    second = await _second_claim(owner_factory, alpha)
    manual = await _second_claim(owner_factory, alpha)
    await _strategy_cite(owner_factory, alpha, manual)
    await _bundle(session_factory, alpha, 1)
    await _save(session_factory, alpha, _multi(alpha, [alpha["approved_id"]]), 2)
    before = await _card(owner_factory, alpha["card_id"])
    with pytest.raises(ConflictError):
        await _save(session_factory, alpha, _multi(alpha, [second]), 2)  # stale revision
    assert await _links(owner_factory, alpha["card_id"]) == sorted(
        [alpha["approved_id"], manual], key=str
    )
    after = await _card(owner_factory, alpha["card_id"])
    assert (after.revision, after.outline) == (before.revision, before.outline)
