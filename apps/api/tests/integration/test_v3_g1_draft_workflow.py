"""Integration tests for V3 G1 review and claim-constrained drafting (handoff §5.2, §6.3).

Runs as the non-superuser application role against PostgreSQL, so RLS applies.
Reuses the Phase 2 two-tenant fixture: each tenant has approved, superseded and
unapproved claims, keyword and prompt demand, a stored page and a planned card.
Model calls use the deterministic ScriptedProvider test double.
"""

import json
from typing import Any
from uuid import UUID

import pytest
from app.ai.provider import GenerationRequest, GenerationResult
from app.core.errors import ConflictError, DomainError, PermissionDenied, ResourceNotFound
from app.domains.audit.models import AuditLog
from app.domains.content_cards.models import ContentCard
from app.domains.content_cards.workflow_schemas import (
    DraftGenerateRequest,
    G1ApproveRequest,
    G1SendBackRequest,
)
from app.domains.content_cards.workflow_service import CardWorkflowService
from app.domains.content_harness.schemas import V3DraftHarnessInput
from app.domains.content_harness.service import ContentHarnessService
from app.domains.job_runs.models import JobRun
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.integration import test_v3_card_workflow as phase2
from tests.integration import test_v3_plan_lock as lock_tests
from tests.unit.test_v3_outline_contract import ScriptedProvider

pytestmark = pytest.mark.integration

db_engine = phase2.db_engine
session_factory = phase2.session_factory
owner_factory = phase2.owner_factory
pair = phase2.pair

WRITER = lock_tests.WRITER_ROLE_ID
VIEWER = lock_tests.VIEWER_ROLE_ID
Factory = async_sessionmaker[AsyncSession]
Pair = tuple[dict[str, Any], dict[str, Any]]


def draft_text(t: dict[str, Any], body: str | None = None) -> str:
    body = body or (
        f"Landed cost is duty plus tax. {t['label']} files IOSS returns "
        f"[CLM:{t['approved_id']}]. Read the [landed cost guide]({t['page_url']})."
    )
    return json.dumps(
        {"schema_version": "v3.draft.v1", "sections": [{"section_id": "s1", "body": body}]}
    )


async def _outlined(factory: Factory, t: dict[str, Any], **section: Any) -> int:
    """planned → bundled → outlined; returns the card revision."""
    await phase2._bundle(factory, t, 1)
    await phase2._save(factory, t, phase2.outline_for(t, **section), 2)
    return 3


async def _approve(factory: Factory, t: dict[str, Any], rev: int, **kw: Any) -> Any:
    async with factory() as session:
        return await CardWorkflowService(session).approve_g1(
            kw.get("org", t["org_id"]), kw.get("project", t["project_id"]),
            kw.get("card", t["card_id"]), G1ApproveRequest(revision=rev),
            actor=kw.get("actor", t["actor"]), request_id="test-g1",
        )  # fmt: skip


async def _send_back(
    factory: Factory, t: dict[str, Any], rev: int, feedback: str = "Lead with duty.", **kw: Any
) -> Any:
    async with factory() as session:
        return await CardWorkflowService(session).send_back_g1(
            t["org_id"], t["project_id"], kw.get("card", t["card_id"]),
            G1SendBackRequest(revision=rev, reason="plan", feedback=feedback),
            actor=kw.get("actor", t["actor"]), request_id="test-g1",
        )  # fmt: skip


async def _draft(factory: Factory, t: dict[str, Any], rev: int, provider: Any, **kw: Any) -> Any:
    async with factory() as session:
        return await CardWorkflowService(session, provider=provider).generate_draft(
            t["org_id"], t["project_id"], kw.get("card", t["card_id"]),
            DraftGenerateRequest(revision=rev), actor=kw.get("actor", t["actor"]),
            request_id="test-draft",
        )  # fmt: skip


async def _runs(factory: Factory, card_id: UUID, job_type: str) -> list[JobRun]:
    async with factory() as session:
        rows = await session.scalars(
            select(JobRun)
            .where(JobRun.entity_id == card_id, JobRun.job_type == job_type)
            .order_by(JobRun.created_at)
        )
        return list(rows)


async def _audit(factory: Factory, card_id: UUID) -> list[str]:
    async with factory() as session:
        rows = await session.scalars(
            select(AuditLog.action)
            .where(AuditLog.resource_id == card_id)
            .order_by(AuditLog.occurred_at)
        )
        return list(rows)


async def _sql(factory: Factory, statement: str, **params: Any) -> None:
    async with factory() as session:
        await session.execute(text(statement), params)
        await session.commit()


async def _card(factory: Factory, card_id: UUID) -> ContentCard:
    return await phase2._card(factory, card_id)


# ── G1: approve / send back ───────────────────────────────────────


@pytest.mark.asyncio
async def test_reviewer_approves_g1_outlined_to_drafting_with_record_and_audit(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _outlined(session_factory, alpha)
    detail = await phase2._detail(session_factory, alpha)
    assert detail.review.status == "awaiting_review" and detail.review.ready
    assert detail.actions.can_review_g1 and not detail.actions.can_generate_draft

    result = await _approve(session_factory, alpha, rev)

    assert result.card.state == "drafting" and result.card.revision == rev + 1
    decision = result.decision
    assert (decision.action, decision.gate, decision.card_revision) == ("approve", "G1", rev)
    assert decision.reviewer_id == alpha["user_id"] and decision.reviewer_name == "Map User Alpha"
    (run,) = await _runs(owner_factory, alpha["card_id"], "v3_gate_decision")
    assert run.triggered_by == str(alpha["user_id"]) and run.input_data is not None
    assert run.input_data["outline"]["sections"][0]["section_id"] == "s1"  # what was approved
    assert "content_card.g1_approved" in await _audit(owner_factory, alpha["card_id"])
    after = await phase2._detail(session_factory, alpha)
    assert after.review.status == "approved" and after.actions.can_generate_draft
    assert not after.actions.can_save_outline  # the approved outline is no longer editable


@pytest.mark.asyncio
async def test_send_back_keeps_outlined_stores_feedback_and_shows_it_next_time(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _outlined(session_factory, alpha)

    result = await _send_back(session_factory, alpha, rev, "Section one needs the duty claim.")

    assert result.card.state == "outlined" and result.card.revision == rev + 1
    assert (result.decision.reason, result.decision.feedback) == (
        "plan",
        "Section one needs the duty claim.",
    )
    detail = await phase2._detail(session_factory, alpha)
    assert detail.review.status == "sent_back"
    assert detail.review.last_decision is not None
    assert detail.review.last_decision.feedback == "Section one needs the duty claim."
    assert detail.actions.can_save_outline  # the writer can revise
    assert "content_card.g1_sent_back" in await _audit(owner_factory, alpha["card_id"])

    # The writer revises; the feedback stays visible and the card is back in review.
    await phase2._save(session_factory, alpha, phase2.outline_for(alpha, heading="Duty"), rev + 1)
    again = await phase2._detail(session_factory, alpha)
    assert again.review.status == "awaiting_review"
    assert again.review.last_decision and again.review.last_decision.action == "send_back"
    approved = await _approve(session_factory, alpha, rev + 2)
    assert approved.card.state == "drafting"
    history = (await phase2._detail(session_factory, alpha)).review.history
    assert [d.action for d in history] == ["approve", "send_back"]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [WRITER, VIEWER])
async def test_writers_and_viewers_cannot_approve_or_send_back(
    role: UUID, session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _outlined(session_factory, alpha)
    await lock_tests._set_role(owner_factory, alpha, role)
    assert not (await phase2._detail(session_factory, alpha)).review.can_review
    with pytest.raises(PermissionDenied):
        await _approve(session_factory, alpha, rev)
    with pytest.raises(PermissionDenied):
        await _send_back(session_factory, alpha, rev)
    card = await _card(owner_factory, alpha["card_id"])
    assert (card.state, card.revision) == ("outlined", rev)
    assert await _runs(owner_factory, alpha["card_id"], "v3_gate_decision") == []


@pytest.mark.asyncio
async def test_named_g1_reviewers_narrow_who_may_decide(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _outlined(session_factory, alpha)
    config = json.dumps({"reviewers": {"G1": ["someone.else@example.test"], "G2": []}})
    await _sql(
        owner_factory,
        "UPDATE projects SET workspace_config = CAST(:c AS jsonb) WHERE id = :p",
        c=config, p=alpha["project_id"],
    )  # fmt: skip
    detail = await phase2._detail(session_factory, alpha)
    assert detail.review.reviewers_restricted and not detail.review.can_review
    with pytest.raises(PermissionDenied):
        await _approve(session_factory, alpha, rev)
    config = json.dumps({"reviewers": {"G1": [alpha["actor"].email], "G2": []}})
    await _sql(
        owner_factory,
        "UPDATE projects SET workspace_config = CAST(:c AS jsonb) WHERE id = :p",
        c=config, p=alpha["project_id"],
    )  # fmt: skip
    assert (await _approve(session_factory, alpha, rev)).card.state == "drafting"


@pytest.mark.asyncio
async def test_g1_revision_conflict_changes_nothing(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _outlined(session_factory, alpha)
    with pytest.raises(ConflictError) as approve:
        await _approve(session_factory, alpha, rev - 1)
    with pytest.raises(ConflictError) as send:
        await _send_back(session_factory, alpha, rev - 1)
    assert approve.value.code == send.value.code == "VERSION_CONFLICT"
    card = await _card(owner_factory, alpha["card_id"])
    assert (card.state, card.revision) == ("outlined", rev)
    assert await _runs(owner_factory, alpha["card_id"], "v3_gate_decision") == []


@pytest.mark.asyncio
async def test_g1_only_applies_to_outlined_cards(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    await phase2._bundle(session_factory, alpha, 1)
    with pytest.raises(ConflictError) as raised:
        await _approve(session_factory, alpha, 2)
    assert raised.value.code == "G1_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_g1_is_tenant_and_project_isolated(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, bravo = pair
    rev = await _outlined(session_factory, alpha)
    # Bravo's reviewer against Alpha's project, and Alpha's card id inside Bravo's scope.
    with pytest.raises(ResourceNotFound):
        await _approve(session_factory, alpha, rev, actor=bravo["actor"])
    with pytest.raises(ResourceNotFound):
        await _approve(session_factory, bravo, rev, card=alpha["card_id"])
    with pytest.raises(ResourceNotFound):
        await _send_back(session_factory, bravo, rev, card=alpha["card_id"])
    assert (await _card(owner_factory, alpha["card_id"])).state == "outlined"


# ── G1 checks ─────────────────────────────────────────────────────


async def _corrupt_outline(factory: Factory, t: dict[str, Any], **section: Any) -> None:
    """Drift the stored outline behind the save validator (data changed since saving)."""
    card = await _card(factory, t["card_id"])
    assert card.outline is not None
    outline = dict(card.outline)
    outline["sections"] = [{**outline["sections"][0], **section}]  # type: ignore[index]
    await _sql(
        factory,
        "UPDATE content_cards SET outline = CAST(:o AS jsonb) WHERE id = :c",
        o=json.dumps(outline, default=str), c=t["card_id"],
    )  # fmt: skip


async def _assert_blocked(factory: Factory, t: dict[str, Any], rev: int, failing: str) -> None:
    detail = await phase2._detail(factory, t)
    assert not detail.review.ready and not detail.actions.can_review_g1
    with pytest.raises(ConflictError) as raised:
        await _approve(factory, t, rev)
    assert raised.value.code == "G1_CHECKS_FAILED"
    assert failing in [c["key"] for c in raised.value.details["checks"]]  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_stale_bundle_blocks_g1(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _outlined(session_factory, alpha)
    await _sql(
        owner_factory, "UPDATE claims SET text = 'Changed' WHERE id = :c", c=alpha["approved_id"]
    )
    await _assert_blocked(session_factory, alpha, rev, "bundle_current")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("section", "failing"),
    [
        ({"claim_ids": ["draft_id"]}, "claims_resolve"),  # unapproved claim
        ({"claim_ids": ["foreign_claim"]}, "claims_resolve"),  # another tenant's claim
        ({"target_demand_id": "foreign_demand"}, "demand_resolves"),
        ({"planned_internal_links": [{"page_id": "foreign_page", "url": "u"}]}, "links_resolve"),
        ({"planned_internal_links": [{"page_id": "page_id", "url": "https://x.test/other"}]},
         "links_resolve"),  # a stored page with an invented URL
        ({"needs_claim": ["a refund figure"]}, "claims_needed"),
    ],
)  # fmt: skip
async def test_invalid_references_block_g1(
    section: dict[str, Any],
    failing: str,
    session_factory: Factory,
    owner_factory: Factory,
    pair: Pair,
) -> None:
    alpha, bravo = pair
    rev = await _outlined(session_factory, alpha)
    ids = {"draft_id": str(alpha["draft_id"]), "foreign_claim": str(bravo["approved_id"]),
           "foreign_demand": str(bravo["demand_id"]), "foreign_page": str(bravo["page_id"]),
           "page_id": str(alpha["page_id"])}  # fmt: skip

    def resolve(value: Any) -> Any:
        if isinstance(value, list):
            return [resolve(v) for v in value]
        if isinstance(value, dict):
            return {k: resolve(v) for k, v in value.items()}
        return ids.get(value, value) if isinstance(value, str) else value

    await _corrupt_outline(owner_factory, alpha, **resolve(section))
    await _assert_blocked(session_factory, alpha, rev, failing)


@pytest.mark.asyncio
async def test_missing_prompt_citable_statement_blocks_g1(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    await _sql(
        owner_factory,
        "UPDATE content_cards SET primary_demand_id = NULL, primary_prompt_id = :p, "
        "secondary_demand_ids = '[]' WHERE id = :c",
        p=alpha["prompt_id"], c=alpha["card_id"],
    )  # fmt: skip
    await phase2._bundle(session_factory, alpha, 1)
    prompt_outline = {
        "primary_mode": "prompt", "title": "Who pays", "prompt_target_id": str(alpha["prompt_id"]),
        "direct_answer": "The importer pays.",
        "sections": [{"section_id": "s1", "order": 1, "heading": "Who pays?",
                      "citable_statement": "The importer pays duty."}],
    }  # fmt: skip
    await phase2._save(session_factory, alpha, prompt_outline, 2)
    await _corrupt_outline(owner_factory, alpha, citable_statement=None)
    await _assert_blocked(session_factory, alpha, 3, "citable_statements")


# ── Draft ─────────────────────────────────────────────────────────


async def _approved(session_factory: Factory, t: dict[str, Any]) -> int:
    rev = await _outlined(session_factory, t)
    await _approve(session_factory, t, rev)
    return rev + 1


@pytest.mark.asyncio
async def test_draft_generates_from_stored_bundle_and_approved_outline(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _approved(session_factory, alpha)
    card = await _card(owner_factory, alpha["card_id"])
    provider = ScriptedProvider(draft_text(alpha))

    result = await _draft(session_factory, alpha, rev, provider)

    stored = result.draft
    assert result.card.state == "drafting" and result.card.revision == rev + 1
    assert stored.version == 1 and stored.bundle_ref == card.bundle_ref
    assert stored.prompt_version == "v3.draft.v1" and stored.source_revision == rev
    section = stored.draft.sections[0]
    assert (
        section.claim_ids == [alpha["approved_id"]]
        and section.heading == "What landed cost includes"
    )
    assert [link.url for link in section.internal_links] == [alpha["page_url"]]
    # The model got the approved outline and the stored bundle's content.
    user = provider.requests[0].messages[1].content
    sent_outline = json.loads(user.split("<outline>\n", 1)[1].split("\n</outline>", 1)[0])
    assert sent_outline == card.outline
    assert str(alpha["approved_id"]) in user and alpha["page_url"] in user
    (run,) = await _runs(owner_factory, alpha["card_id"], "v3_draft_generation")
    assert (run.status, run.prompt_version, run.provider, run.total_tokens) == (
        "completed", "v3.draft.v1", "scripted", 150,
    )  # fmt: skip
    assert run.input_data and run.input_data["bundle_ref"] == str(card.bundle_ref)
    assert run.output_data and run.output_data["stored"] is True
    assert "content_card.draft_generated" in await _audit(owner_factory, alpha["card_id"])
    detail = await phase2._detail(session_factory, alpha)
    assert detail.draft is not None and detail.draft.version == 1
    assert detail.last_draft_run and detail.last_draft_run.stored


@pytest.mark.asyncio
async def test_draft_requires_g1_approval(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _outlined(session_factory, alpha)
    provider = ScriptedProvider(draft_text(alpha))
    with pytest.raises(ConflictError) as raised:
        await _draft(session_factory, alpha, rev, provider)
    assert raised.value.code == "G1_APPROVAL_REQUIRED" and provider.requests == []


@pytest.mark.asyncio
async def test_stale_bundle_blocks_drafting_until_rebuilt(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _approved(session_factory, alpha)
    await _sql(
        owner_factory, "UPDATE claims SET text = 'Changed' WHERE id = :c", c=alpha["approved_id"]
    )
    provider = ScriptedProvider(draft_text(alpha))
    with pytest.raises(ConflictError) as raised:
        await _draft(session_factory, alpha, rev, provider)
    assert raised.value.code == "BUNDLE_STALE" and provider.requests == []
    assert not (await phase2._detail(session_factory, alpha)).actions.can_generate_draft
    await phase2._bundle(session_factory, alpha, rev)  # rebuilding is allowed in drafting
    card = await _card(owner_factory, alpha["card_id"])
    assert card.state == "drafting"
    assert (await _draft(session_factory, alpha, card.revision, provider)).draft.version == 1


@pytest.mark.asyncio
async def test_invalid_output_is_retried_once_and_never_replaces_a_valid_draft(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, bravo = pair
    rev = await _approved(session_factory, alpha)
    first = await _draft(session_factory, alpha, rev, ScriptedProvider(draft_text(alpha)))
    before = (await _card(owner_factory, alpha["card_id"])).draft

    # A cross-tenant claim id and another tenant's URL: both rejected, twice.
    hostile = draft_text(alpha, f"We win [CLM:{bravo['approved_id']}]. [x]({bravo['page_url']})")
    provider = ScriptedProvider(hostile, "not json at all")
    with pytest.raises(DomainError) as raised:
        await _draft(session_factory, alpha, first.card.revision, provider)

    assert raised.value.code == "DRAFT_INVALID" and len(provider.requests) == 2
    card = await _card(owner_factory, alpha["card_id"])
    assert card.draft == before and card.revision == first.card.revision
    runs = await _runs(owner_factory, alpha["card_id"], "v3_draft_generation")
    assert [r.status for r in runs] == ["completed", "failed"]
    assert runs[1].output_data and runs[1].output_data["stored"] is False
    detail = await phase2._detail(session_factory, alpha)
    assert detail.last_draft_run and detail.last_draft_run.status == "failed"
    attempts: list[dict[str, Any]] = runs[1].output_data["attempts"]  # type: ignore[assignment]
    first_codes = {issue["code"] for issue in attempts[0]["issues"]}
    assert {"CLAIM_NOT_IN_OUTLINE", "INVENTED_URL"} <= first_codes


@pytest.mark.asyncio
async def test_provider_failure_records_a_failed_job_and_keeps_the_card(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _approved(session_factory, alpha)
    with pytest.raises(DomainError) as raised:
        await _draft(session_factory, alpha, rev, ScriptedProvider(fail=RuntimeError("quota")))
    assert raised.value.code == "AI_PROVIDER_ERROR"
    card = await _card(owner_factory, alpha["card_id"])
    assert (card.state, card.revision, card.draft) == ("drafting", rev, None)
    (run,) = await _runs(owner_factory, alpha["card_id"], "v3_draft_generation")
    assert run.status == "failed" and run.error


@pytest.mark.asyncio
async def test_draft_revision_conflicts_before_and_during_generation(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _approved(session_factory, alpha)
    provider = ScriptedProvider(draft_text(alpha))
    with pytest.raises(ConflictError):
        await _draft(session_factory, alpha, rev - 1, provider)
    assert provider.requests == []

    class ConcurrentEdit(ScriptedProvider):
        async def generate(self, request: GenerationRequest) -> GenerationResult:
            bump = "UPDATE content_cards SET revision = revision + 1 WHERE id = :c"
            await _sql(owner_factory, bump, c=alpha["card_id"])
            return await super().generate(request)

    with pytest.raises(ConflictError) as raised:
        await _draft(session_factory, alpha, rev, ConcurrentEdit(draft_text(alpha)))
    assert raised.value.code == "VERSION_CONFLICT"
    assert (await _card(owner_factory, alpha["card_id"])).draft is None
    (run,) = await _runs(owner_factory, alpha["card_id"], "v3_draft_generation")
    assert (
        run.output_data
        and run.output_data["stored"] is False
        and "VERSION_CONFLICT" in (run.error or "")
    )


@pytest.mark.asyncio
async def test_draft_is_tenant_isolated_and_needs_write_permission(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, bravo = pair
    rev = await _approved(session_factory, alpha)
    provider = ScriptedProvider(draft_text(alpha))
    with pytest.raises(ResourceNotFound):
        await _draft(session_factory, alpha, rev, provider, actor=bravo["actor"])
    with pytest.raises(ResourceNotFound):
        await _draft(session_factory, bravo, rev, provider, card=alpha["card_id"])
    await lock_tests._set_role(owner_factory, alpha, VIEWER)
    with pytest.raises(PermissionDenied):
        await _draft(session_factory, alpha, rev, provider)
    assert provider.requests == []
    assert (await _card(owner_factory, alpha["card_id"])).draft is None


# ── Harness ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_harness_runs_the_production_draft_contract_without_touching_the_card(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _approved(session_factory, alpha)
    production = ScriptedProvider(draft_text(alpha))
    await _draft(session_factory, alpha, rev, production)
    card_before = await _card(owner_factory, alpha["card_id"])

    harness = ScriptedProvider(draft_text(alpha))
    async with session_factory() as session, session.begin():
        detail = await ContentHarnessService(provider=harness).run_v3_draft(
            session,
            actor=alpha["actor"],
            input_data=V3DraftHarnessInput(
                project_id=alpha["project_id"], card_id=alpha["card_id"]
            ),
        )
    assert detail.prompt_version == "v3.draft.v1" and detail.input_data["mode"] == "v3_draft"
    assert detail.evaluation_data and detail.evaluation_data["status"] == "PASS"
    # Same prompt, outline and context as production.
    assert harness.requests[0].messages == production.requests[0].messages
    card_after = await _card(owner_factory, alpha["card_id"])
    assert (card_after.revision, card_after.draft) == (card_before.revision, card_before.draft)
