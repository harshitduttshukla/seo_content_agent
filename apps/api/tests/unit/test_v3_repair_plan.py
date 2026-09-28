"""Unit tests for the shared repair plan: which QA errors a repair run can fix, and how."""

from datetime import UTC, datetime
from uuid import uuid4

from app.domains.content_cards.draft import DraftSection, DraftV3, StoredDraft
from app.domains.content_cards.production_state import MIN_SECTION_WORDS, repair_plan
from app.domains.content_cards.qa import QAFinding, QAReport


def _draft(*bodies: str) -> StoredDraft:
    sections = [
        DraftSection(section_id=f"s{i}", order=i, heading=f"H{i}", body=body)
        for i, body in enumerate(bodies, start=1)
    ]
    draft = DraftV3(primary_mode="keyword", title="T", sections=sections)
    # repair_plan reads only the draft body; provenance fields are irrelevant here.
    return StoredDraft.model_construct(version=1, draft=draft, job_run_id=uuid4())


def _report(*findings: QAFinding) -> QAReport:
    return QAReport(
        status="failed",
        run_at=datetime.now(UTC),
        job_run_id=uuid4(),
        card_revision=1,
        draft_version=1,
        bundle_ref=uuid4(),
        bundle_hash="h",
        findings=list(findings),
        model_layer="skipped",
    )


def _finding(code: str, section_id: str | None = None, severity: str = "error") -> QAFinding:
    return QAFinding(
        id=f"{code}-{section_id}",
        code=code,
        severity=severity,  # type: ignore[arg-type]
        layer="deterministic",
        message=code,
        section_id=section_id,
    )


def _words(n: int) -> str:
    return " ".join(["word"] * n)


def test_a_short_page_expands_every_section_in_proportion() -> None:
    draft = _draft(_words(300), _words(100))  # 400 words against a 1000 budget
    plan = repair_plan(_report(_finding("WORD_BUDGET")), draft, 1000)

    assert plan is not None and plan.targets == ["s1", "s2"]
    targets = {i["section_id"]: i["target_words"] for i in plan.instructions}
    assert targets == {"s1": 750, "s2": 250}  # the same 2.5x factor, summing to the budget
    assert all(str(i["message"]).startswith("Expand") for i in plan.instructions)


def test_a_long_page_trims_but_never_below_the_section_floor() -> None:
    draft = _draft(_words(2000), _words(20))
    plan = repair_plan(_report(_finding("WORD_BUDGET")), draft, 1000)

    assert plan is not None
    targets = {i["section_id"]: i["target_words"] for i in plan.instructions}
    assert targets["s1"] < 2000 and targets["s2"] == MIN_SECTION_WORDS
    assert str(plan.instructions[0]["message"]).startswith("Trim")


def test_claim_markers_do_not_count_as_words() -> None:
    draft = _draft(_words(100) + " [CLM:abc] [CLM:def]", _words(100))
    plan = repair_plan(_report(_finding("WORD_BUDGET")), draft, 400)
    assert plan is not None
    assert {i["target_words"] for i in plan.instructions} == {200}


def test_section_errors_still_target_only_their_section() -> None:
    plan = repair_plan(_report(_finding("UNMARKED_ASSERTION", "s2")), _draft("a", "b"), 1000)
    assert plan is not None and plan.targets == ["s2"] and plan.instructions == []


def test_errors_outside_the_draft_text_cannot_be_repaired() -> None:
    report = _report(_finding("CLAIM_SUPERSEDED"), _finding("WORD_BUDGET", severity="warning"))
    assert repair_plan(report, _draft("a"), 1000) is None
    # Without a budget the length error has nothing to aim at.
    assert repair_plan(_report(_finding("WORD_BUDGET")), _draft("a"), None) is None
    assert repair_plan(None, _draft("a"), 1000) is None
