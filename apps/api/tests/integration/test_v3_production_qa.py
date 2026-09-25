"""Integration tests for V3 Production QA, repair, section regeneration and G2 (Phase 4).

Runs as the non-superuser application role against PostgreSQL, so RLS applies.
Reuses the Phase 2 two-tenant fixture. Model calls use the ScriptedProvider test
double; nothing here calls a paid provider.
"""

import json
from typing import Any
from uuid import UUID

import pytest
from app.core.errors import ConflictError, DomainError, PermissionDenied, ResourceNotFound
from app.domains.content_cards.production_service import ProductionService
from app.domains.content_cards.workflow_schemas import (
    G2ApproveRequest,
    G2SendBackRequest,
    QARunRequest,
    RepairRequest,
    SectionRegenerateRequest,
    WarningDismissRequest,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.integration import test_v3_card_workflow as phase2
from tests.integration import test_v3_g1_draft_workflow as phase3
from tests.integration import test_v3_plan_lock as lock_tests
from tests.unit.test_v3_outline_contract import ScriptedProvider

pytestmark = pytest.mark.integration

db_engine = phase2.db_engine
session_factory = phase2.session_factory
owner_factory = phase2.owner_factory
pair = phase2.pair

Factory = async_sessionmaker[AsyncSession]
Pair = tuple[dict[str, Any], dict[str, Any]]
CLEAN_QA = json.dumps({"schema_version": "v3.qa.v1", "findings": []})
S2_BODY = "Duty is charged on the customs value of each item in the order."


def s1_body(t: dict[str, Any]) -> str:
    return (
        f"Landed cost is duty plus tax. {t['label']} files IOSS returns "
        f"[CLM:{t['approved_id']}]. Read the [landed cost guide]({t['page_url']})."
    )


def two_section_draft(t: dict[str, Any], s1: str | None = None, s2: str = S2_BODY) -> str:
    return json.dumps(
        {
            "schema_version": "v3.draft.v1",
            "sections": [
                {"section_id": "s1", "body": s1 or s1_body(t)},
                {"section_id": "s2", "body": s2},
            ],
        }
    )


def section_json(**bodies: str) -> str:
    return json.dumps(
        {
            "schema_version": "v3.draft.v1",
            "sections": [{"section_id": k, "body": v} for k, v in bodies.items()],
        }
    )


async def _drafted(sf: Factory, t: dict[str, Any]) -> int:
    """planned → … → drafting with a stored two-section draft; returns the revision."""
    await phase2._bundle(sf, t, 1)
    outline = phase2.outline_for(t)
    outline["sections"].append({"section_id": "s2", "order": 2, "heading": "How duty is charged"})
    await phase2._save(sf, t, outline, 2)
    await phase3._approve(sf, t, 3)
    result = await phase3._draft(sf, t, 4, ScriptedProvider(two_section_draft(t)))
    return int(result.card.revision)


def _svc(session: AsyncSession, *texts: str, fail: Exception | None = None) -> ProductionService:
    return ProductionService(session, provider=ScriptedProvider(*texts, fail=fail))


async def _qa(sf: Factory, t: dict[str, Any], rev: int, *texts: str, **kw: Any) -> Any:
    provider = kw.pop("provider", None) or ScriptedProvider(*texts, fail=kw.pop("fail", None))
    async with sf() as session:
        return await ProductionService(session, provider=provider).run_qa(
            t["org_id"],
            t["project_id"],
            kw.get("card", t["card_id"]),
            QARunRequest(revision=rev),
            actor=kw.get("actor", t["actor"]),
            request_id="qa",
        )


async def _repair(sf: Factory, t: dict[str, Any], rev: int, *texts: str) -> Any:
    async with sf() as session:
        return await _svc(session, *texts).repair_draft(
            t["org_id"],
            t["project_id"],
            t["card_id"],
            RepairRequest(revision=rev),
            actor=t["actor"],
            request_id="repair",
        )


async def _regen(sf: Factory, t: dict[str, Any], rev: int, section: str, *texts: str) -> Any:
    async with sf() as session:
        return await _svc(session, *texts).regenerate_section(
            t["org_id"],
            t["project_id"],
            t["card_id"],
            section,
            SectionRegenerateRequest(revision=rev, feedback="Make it shorter."),
            actor=t["actor"],
            request_id="regen",
        )


async def _g2(sf: Factory, t: dict[str, Any], action: str, rev: int, **kw: Any) -> Any:
    async with sf() as session:
        svc = ProductionService(session)
        actor = kw.get("actor", t["actor"])
        args = (t["org_id"], t["project_id"], kw.get("card", t["card_id"]))
        if action == "approve":
            return await svc.approve_g2(
                *args, G2ApproveRequest(revision=rev), actor=actor, request_id="g2"
            )
        if action == "send_back":
            return await svc.send_back_g2(
                *args,
                G2SendBackRequest(revision=rev, reason="writer", feedback="Tighten s2."),
                actor=actor,
                request_id="g2",
            )
        return await svc.dismiss_warning(
            *args,
            WarningDismissRequest(revision=rev, finding_id=kw["finding"], reason="Fine here."),
            actor=actor,
            request_id="g2",
        )


async def _set_body(factory: Factory, t: dict[str, Any], section: int, body: str) -> None:
    await phase3._sql(
        factory,
        "UPDATE content_cards SET draft = jsonb_set(draft, CAST(:path AS text[]), "
        "to_jsonb(CAST(:b AS text))) WHERE id = :c",
        path=["draft", "sections", str(section), "body"],
        b=body,
        c=t["card_id"],
    )


async def _card(factory: Factory, t: dict[str, Any]) -> Any:
    return await phase2._card(factory, t["card_id"])


async def _dismiss_all_warnings(sf: Factory, t: dict[str, Any], rev: int) -> int:
    detail = await phase2._detail(sf, t)
    assert detail.g2 is not None
    for finding_id in detail.g2.pending_warning_ids:
        rev = (await _g2(sf, t, "dismiss", rev, finding=finding_id)).card.revision
    return rev


# ── QA ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_grounded_draft_passes_qa_with_a_stored_current_report(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    provider = ScriptedProvider(CLEAN_QA)

    result = await _qa(session_factory, alpha, rev, provider=provider)

    report = result.report
    assert result.card.state == "qa_passed" and report.status == "passed"
    assert report.card_revision == result.card.revision and report.draft_version == 1
    assert report.error_count == 0 and report.model_layer == "ran"
    assert len(provider.requests) == 1  # model layer ran once
    assert "<draft>" in provider.requests[0].messages[1].content
    (run,) = await phase3._runs(owner_factory, alpha["card_id"], "v3_qa")
    assert run.status == "completed" and run.prompt_version == "v3.qa.v1"
    assert "content_card.qa_run" in await phase3._audit(owner_factory, alpha["card_id"])
    detail = await phase2._detail(session_factory, alpha)
    assert detail.qa and detail.qa.report and not detail.qa.stale
    assert detail.g2 and detail.g2.status == "awaiting_review"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda t: ("s1", s1_body(t).replace(f" [CLM:{t['approved_id']}]", "")),
            "MISSING_CLAIM_MARKER",
        ),
        (lambda t: ("s1", s1_body(t) + " We win [CLM:{b}]."), "CLAIM_NOT_IN_OUTLINE"),
        (
            lambda t: ("s1", s1_body(t).replace(f"({t['page_url']})", "(https://invented.test/x)")),
            "INVENTED_URL",
        ),
        (
            lambda t: (
                "s1",
                s1_body(t).replace(f"[landed cost guide]({t['page_url']})", "the guide"),
            ),
            "MISSING_PLANNED_LINK",
        ),
        (lambda t: ("s2", S2_BODY + " It is never cheap."), "BANNED_WORD"),
        (lambda t: ("s2", S2_BODY + " [NEEDS-CLAIM: refund reduction figure]"), "NEEDS_CLAIM"),
        (lambda t: ("s2", "## A new top-level section\n" + S2_BODY), "STRUCTURE_CHANGED"),
    ],
)
async def test_deterministic_errors_fail_qa_without_calling_the_model(
    mutate: Any, code: str, session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, bravo = pair
    rev = await _drafted(session_factory, alpha)
    section, body = mutate(alpha)
    await _set_body(
        owner_factory,
        alpha,
        0 if section == "s1" else 1,
        body.replace("{b}", str(bravo["approved_id"])),
    )
    provider = ScriptedProvider(CLEAN_QA)

    result = await _qa(session_factory, alpha, rev, provider=provider)

    assert result.card.state == "qa_failed" and result.report.status == "failed"
    assert code in {f.code for f in result.report.findings if f.severity == "error"}
    assert result.report.model_layer == "skipped" and provider.requests == []


@pytest.mark.asyncio
async def test_superseded_claim_fails_qa_after_the_bundle_is_rebuilt(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    await phase3._sql(
        owner_factory, "UPDATE claims SET superseded_by = id WHERE id = :c", c=alpha["approved_id"]
    )
    with pytest.raises(ConflictError) as stale:
        await _qa(session_factory, alpha, rev, CLEAN_QA)
    assert stale.value.code == "BUNDLE_STALE"
    await phase2._bundle(session_factory, alpha, rev)  # rebuilding is allowed while drafting
    rev = (await _card(owner_factory, alpha)).revision
    result = await _qa(session_factory, alpha, rev, CLEAN_QA)
    codes = {f.code for f in result.report.findings if f.severity == "error"}
    assert {"STALE_REFERENCE", "STALE_CLAIM"} <= codes and result.card.state == "qa_failed"


@pytest.mark.asyncio
async def test_model_findings_are_validated_and_only_grounding_blocks(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    tone = {"type": "tone", "section_id": "s2", "evidence": "customs value", "reason": "flat"}
    result = await _qa(
        session_factory, alpha, rev, json.dumps({"schema_version": "v3.qa.v1", "findings": [tone]})
    )
    (finding,) = [f for f in result.report.findings if f.layer == "model"]
    assert (finding.code, finding.severity) == ("TONE", "warning")  # severity is policy
    assert result.card.state == "qa_passed"


@pytest.mark.asyncio
async def test_unsupported_assertion_from_the_model_fails_qa(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    finding = {
        "type": "unsupported_assertion",
        "section_id": "s2",
        "evidence": "Duty is charged on the customs value",
        "reason": "company claim",
        "suggested_repair": "cite a claim",
    }
    result = await _qa(
        session_factory,
        alpha,
        rev,
        json.dumps({"schema_version": "v3.qa.v1", "findings": [finding]}),
    )
    assert result.card.state == "qa_failed"
    assert [f.code for f in result.report.findings if f.severity == "error"] == [
        "UNSUPPORTED_ASSERTION"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        json.dumps(
            {"findings": [{"type": "tone", "section_id": "s9", "evidence": "x", "reason": "r"}]}
        ),
        json.dumps(
            {
                "findings": [
                    {
                        "type": "tone",
                        "section_id": "s2",
                        "evidence": "invented quote",
                        "reason": "r",
                    }
                ]
            }
        ),
        json.dumps(
            {
                "findings": [
                    {
                        "type": "claim_mismatch",
                        "section_id": "s2",
                        "evidence": "customs value",
                        "reason": "r",
                        "claim_id": "11111111-1111-1111-1111-111111111111",
                    }
                ]
            }
        ),
    ],
)
async def test_invalid_model_output_is_retried_once_then_changes_nothing(
    bad: str, session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    provider = ScriptedProvider(bad, bad, bad)
    with pytest.raises(DomainError) as raised:
        await _qa(session_factory, alpha, rev, provider=provider)
    assert raised.value.code == "QA_OUTPUT_INVALID" and len(provider.requests) == 2
    card = await _card(owner_factory, alpha)
    assert (card.state, card.revision, card.qa_report) == ("drafting", rev, None)
    (run,) = await phase3._runs(owner_factory, alpha["card_id"], "v3_qa")
    assert run.status == "failed"


@pytest.mark.asyncio
async def test_provider_failure_during_qa_changes_nothing(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    with pytest.raises(DomainError) as raised:
        await _qa(session_factory, alpha, rev, fail=RuntimeError("overloaded"))
    assert raised.value.code == "AI_PROVIDER_ERROR"
    card = await _card(owner_factory, alpha)
    assert (card.state, card.revision) == ("drafting", rev)


@pytest.mark.asyncio
async def test_qa_permissions_conflicts_and_isolation(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, bravo = pair
    rev = await _drafted(session_factory, alpha)
    with pytest.raises(ConflictError):
        await _qa(session_factory, alpha, rev - 1, CLEAN_QA)
    with pytest.raises(ResourceNotFound):
        await _qa(session_factory, alpha, rev, CLEAN_QA, actor=bravo["actor"])
    with pytest.raises(ResourceNotFound):
        await _qa(session_factory, bravo, rev, CLEAN_QA, card=alpha["card_id"])
    await lock_tests._set_role(owner_factory, alpha, lock_tests.VIEWER_ROLE_ID)
    with pytest.raises(PermissionDenied):
        await _qa(session_factory, alpha, rev, CLEAN_QA)
    assert (await _card(owner_factory, alpha)).state == "drafting"


# ── Repair ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_repair_fixes_only_failing_sections_then_qa_passes(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    broken = s1_body(alpha).replace(f" [CLM:{alpha['approved_id']}]", "")
    await _set_body(owner_factory, alpha, 0, broken)
    failed = await _qa(session_factory, alpha, rev, CLEAN_QA)
    assert failed.card.state == "qa_failed"

    repaired = await _repair(
        session_factory, alpha, failed.card.revision, section_json(s1=s1_body(alpha))
    )

    draft = repaired.draft
    assert repaired.card.state == "drafting" and draft.version == 2
    assert (draft.generation_type, draft.previous_version) == ("repair", 1)
    assert draft.trigger["sections"] == ["s1"]
    assert draft.draft.sections[1].body == S2_BODY  # untouched
    detail = await phase2._detail(session_factory, alpha)
    assert detail.qa and detail.qa.stale  # QA must run again
    (run,) = await phase3._runs(owner_factory, alpha["card_id"], "v3_draft_repair")
    assert run.status == "completed" and run.input_data and run.input_data["previous_draft"]
    passed = await _qa(session_factory, alpha, repaired.card.revision, CLEAN_QA)
    assert passed.card.state == "qa_passed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [
        lambda t: section_json(s1=s1_body(t), s2="Rewritten too."),  # out of scope
        lambda t: section_json(s1=s1_body(t) + " We win [CLM:{b}]."),  # other tenant's claim
        lambda t: section_json(s1=s1_body(t).replace(t["page_url"], "https://x.test/p")),
        lambda t: section_json(s1="## New section\n" + s1_body(t)),
    ],
)
async def test_invalid_repairs_are_rejected_and_the_draft_is_kept(
    bad: Any, session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, bravo = pair
    rev = await _drafted(session_factory, alpha)
    await _set_body(
        owner_factory, alpha, 0, s1_body(alpha).replace(f" [CLM:{alpha['approved_id']}]", "")
    )
    failed = await _qa(session_factory, alpha, rev, CLEAN_QA)
    before = (await _card(owner_factory, alpha)).draft
    text_ = bad(alpha).replace("{b}", str(bravo["approved_id"]))
    with pytest.raises(DomainError) as raised:
        await _repair(session_factory, alpha, failed.card.revision, text_, text_)
    assert raised.value.code == "REVISION_INVALID"
    card = await _card(owner_factory, alpha)
    assert (card.draft, card.state, card.revision) == (before, "qa_failed", failed.card.revision)
    (run,) = await phase3._runs(owner_factory, alpha["card_id"], "v3_draft_repair")
    assert run.status == "failed"


@pytest.mark.asyncio
async def test_repair_requires_a_current_failed_report_and_the_revision(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    with pytest.raises(ConflictError) as not_failed:
        await _repair(session_factory, alpha, rev, section_json(s1=s1_body(alpha)))
    assert not_failed.value.code == "REPAIR_NOT_ALLOWED"
    await _set_body(
        owner_factory, alpha, 0, s1_body(alpha).replace(f" [CLM:{alpha['approved_id']}]", "")
    )
    failed = await _qa(session_factory, alpha, rev, CLEAN_QA)
    with pytest.raises(ConflictError) as stale:
        await _repair(session_factory, alpha, failed.card.revision - 1, section_json(s1="x"))
    assert stale.value.code == "VERSION_CONFLICT"


# ── Section regeneration ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_section_regeneration_changes_one_section_and_makes_qa_stale(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    passed = await _qa(session_factory, alpha, rev, CLEAN_QA)
    before = (await _card(owner_factory, alpha)).draft

    result = await _regen(
        session_factory,
        alpha,
        passed.card.revision,
        "s2",
        section_json(s2="Duty is charged per item."),
    )

    assert result.card.state == "drafting" and result.card.revision == passed.card.revision + 1
    assert result.draft.version == 2 and result.draft.generation_type == "section_regeneration"
    assert result.draft.draft.sections[0].body == before["draft"]["sections"][0]["body"]
    assert result.draft.draft.sections[1].body == "Duty is charged per item."
    detail = await phase2._detail(session_factory, alpha)
    assert detail.qa and detail.qa.stale and detail.g2 and not detail.g2.ready
    with pytest.raises(ResourceNotFound):
        await _regen(session_factory, alpha, result.card.revision, "s9", section_json(s9="x"))
    # An unapproved claim the outline never attached is rejected, and nothing changes.
    bad = section_json(s2=f"We [CLM:{alpha['draft_id']}].")
    with pytest.raises(DomainError) as raised:
        await _regen(session_factory, alpha, result.card.revision, "s2", bad, bad)
    assert raised.value.code == "REVISION_INVALID"
    assert (await _card(owner_factory, alpha)).revision == result.card.revision


# ── G2 ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_g2_requires_dismissed_warnings_then_approves_with_snapshots(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    passed = await _qa(session_factory, alpha, rev, CLEAN_QA)
    warnings = [f for f in passed.report.findings if f.severity == "warning"]
    assert warnings  # e.g. the workspace word budget and demand placement
    with pytest.raises(ConflictError) as blocked:
        await _g2(session_factory, alpha, "approve", passed.card.revision)
    assert blocked.value.code == "G2_BLOCKED"

    rev = await _dismiss_all_warnings(session_factory, alpha, passed.card.revision)
    detail = await phase2._detail(session_factory, alpha)
    assert detail.qa and not detail.qa.stale and detail.qa.report
    assert len(detail.qa.report.dismissals) == len(warnings)  # history is kept
    result = await _g2(session_factory, alpha, "approve", rev)

    assert result.card.state == "approved" and result.decision.gate == "G2"
    runs = [
        r
        for r in await phase3._runs(owner_factory, alpha["card_id"], "v3_gate_decision")
        if (r.input_data or {}).get("gate") == "G2"
    ]
    (run,) = runs
    assert run.input_data and run.input_data["qa_report"]["status"] == "passed"
    assert run.input_data["draft_version"] == 1
    audit = await phase3._audit(owner_factory, alpha["card_id"])
    assert "content_card.g2_approved" in audit and "content_card.qa_warning_dismissed" in audit


@pytest.mark.asyncio
async def test_errors_cannot_be_dismissed_and_stale_qa_blocks_g2(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    passed = await _qa(session_factory, alpha, rev, CLEAN_QA)
    with pytest.raises(ResourceNotFound):
        await _g2(session_factory, alpha, "dismiss", passed.card.revision, finding="nope")
    # The card moves on without QA re-running: G2 must refuse the old report.
    await phase3._sql(
        owner_factory,
        "UPDATE content_cards SET revision = revision + 1 WHERE id = :c",
        c=alpha["card_id"],
    )
    with pytest.raises(ConflictError) as stale:
        await _g2(session_factory, alpha, "approve", passed.card.revision + 1)
    assert stale.value.code == "G2_BLOCKED" and "stale" in stale.value.message


@pytest.mark.asyncio
async def test_g2_send_back_returns_to_drafting_with_feedback(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    passed = await _qa(session_factory, alpha, rev, CLEAN_QA)
    result = await _g2(session_factory, alpha, "send_back", passed.card.revision)
    assert result.card.state == "drafting" and result.decision.feedback == "Tighten s2."
    detail = await phase2._detail(session_factory, alpha)
    assert detail.g2 and detail.g2.status == "sent_back"
    assert detail.g2.last_decision and detail.g2.last_decision.reason == "writer"
    assert detail.review.last_decision and detail.review.last_decision.gate == "G1"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [lock_tests.WRITER_ROLE_ID, lock_tests.VIEWER_ROLE_ID])
async def test_writers_and_viewers_cannot_decide_g2(
    role: UUID, session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    passed = await _qa(session_factory, alpha, rev, CLEAN_QA)
    await lock_tests._set_role(owner_factory, alpha, role)
    for action in ("approve", "send_back"):
        with pytest.raises(PermissionDenied):
            await _g2(session_factory, alpha, action, passed.card.revision)
    with pytest.raises(PermissionDenied):
        await _g2(session_factory, alpha, "dismiss", passed.card.revision, finding="x")
    assert (await _card(owner_factory, alpha)).state == "qa_passed"


@pytest.mark.asyncio
async def test_g2_is_tenant_isolated(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, bravo = pair
    rev = await _drafted(session_factory, alpha)
    passed = await _qa(session_factory, alpha, rev, CLEAN_QA)
    with pytest.raises(ResourceNotFound):
        await _g2(session_factory, alpha, "approve", passed.card.revision, actor=bravo["actor"])
    with pytest.raises(ResourceNotFound):
        await _g2(session_factory, bravo, "approve", passed.card.revision, card=alpha["card_id"])
    assert (await _card(owner_factory, alpha)).state == "qa_passed"


# ── Harness ───────────────────────────────────────────────────────


async def _harness(sf: Factory, t: dict[str, Any], provider: Any, **fields: Any) -> Any:
    from app.domains.content_harness.schemas import V3ProductionHarnessInput
    from app.domains.content_harness.service import ContentHarnessService

    async with sf() as session, session.begin():
        return await ContentHarnessService(provider=provider).run_v3_production(
            session,
            actor=t["actor"],
            input_data=V3ProductionHarnessInput(
                project_id=t["project_id"], card_id=t["card_id"], **fields
            ),
        )


@pytest.mark.asyncio
async def test_harness_shares_the_production_qa_path_without_touching_the_card(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    rev = await _drafted(session_factory, alpha)
    before = await _card(owner_factory, alpha)
    harness = ScriptedProvider(CLEAN_QA)
    detail = await _harness(session_factory, alpha, harness, mode="qa")
    assert detail.input_data["mode"] == "v3_qa" and detail.prompt_version == "v3.qa.v1"
    assert detail.evaluation_data and detail.evaluation_data["status"] == "PASS"
    after = await _card(owner_factory, alpha)
    assert (after.state, after.revision, after.qa_report) == ("drafting", rev, before.qa_report)

    production = ScriptedProvider(CLEAN_QA)
    await _qa(session_factory, alpha, rev, provider=production)
    assert harness.requests[0].messages == production.requests[0].messages


@pytest.mark.asyncio
async def test_harness_scores_repair_and_section_regeneration(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    await _drafted(session_factory, alpha)
    await _set_body(
        owner_factory, alpha, 0, s1_body(alpha).replace(f" [CLM:{alpha['approved_id']}]", "")
    )
    repair = await _harness(
        session_factory, alpha, ScriptedProvider(section_json(s1=s1_body(alpha))), mode="repair"
    )
    rules = {f["rule"]: f["status"] for f in repair.evaluation_data["findings"]}
    assert rules["fixes_intended_findings"] == "PASS"
    assert rules["unrelated_sections_unchanged"] == "PASS"

    bad = section_json(s1=s1_body(alpha), s2="Also rewritten.")
    rejected = await _harness(session_factory, alpha, ScriptedProvider(bad, bad), mode="repair")
    rules = {f["rule"]: f["status"] for f in rejected.evaluation_data["findings"]}
    assert rules["structured_output"] == "FAIL" and rules["preserves_outline"] == "FAIL"

    section = await _harness(
        session_factory,
        alpha,
        ScriptedProvider(section_json(s2="Shorter s2.")),
        mode="section",
        section_id="s2",
        feedback="shorter",
    )
    assert section.prompt_version == "v3.section.v1"
    rules = {f["rule"]: f["status"] for f in section.evaluation_data["findings"]}
    assert rules["unrelated_sections_unchanged"] == "PASS"
    card = await _card(owner_factory, alpha)
    assert card.state == "drafting" and card.draft["version"] == 1
