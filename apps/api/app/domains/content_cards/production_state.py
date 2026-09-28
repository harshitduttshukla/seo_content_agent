"""Pure read-side rules for V3 QA freshness and G2 readiness (handoff §5.2, §6.4).

One definition shared by the card detail view and the G2/QA write paths, so the UI
and the server never disagree about whether QA is current or G2 may pass.
"""

from dataclasses import dataclass, field

from app.domains.canvas.schemas import WorkspaceConfig
from app.domains.content_cards.draft import ANY_CLAIM_MARKER, StoredDraft
from app.domains.content_cards.models import ContentCard
from app.domains.content_cards.outline import word_count
from app.domains.content_cards.qa import QAReport
from app.domains.content_cards.schemas import ContentCardState
from app.domains.content_cards.workflow_schemas import (
    BundleStatus,
    G2Status,
    GateDecision,
)
from pydantic import ValidationError

QA_STATES = {ContentCardState.DRAFTING, ContentCardState.QA_FAILED}
REGENERATE_STATES = {
    ContentCardState.DRAFTING,
    ContentCardState.QA_FAILED,
    ContentCardState.QA_PASSED,
}


def stored_qa_report(card: ContentCard) -> QAReport | None:
    if card.qa_report is None:
        return None
    try:
        return QAReport.from_stored(card.qa_report)
    except ValidationError:
        return None


def qa_is_current(card: ContentCard, report: QAReport | None, draft: StoredDraft | None) -> bool:
    """A report is current only for this exact card revision and draft version."""
    return (
        report is not None
        and draft is not None
        and report.card_revision == card.revision
        and report.draft_version == draft.version
    )


def card_word_budget(card: ContentCard, config: WorkspaceConfig) -> tuple[int | None, bool]:
    """The card's word budget and whether it is the card's own (hard) or a workspace default."""
    if card.word_budget:
        return card.word_budget, True
    default = getattr(config.word_budgets, card.kind, None)
    return (default, False) if isinstance(default, int) and default > 0 else (None, False)


# A section is never asked to shrink below this, so trimming keeps every section readable.
MIN_SECTION_WORDS = 40


@dataclass(frozen=True)
class RepairPlan:
    """What a repair run rewrites: the sections, the direct answer, and why."""

    targets: list[str]
    fix_direct_answer: bool
    instructions: list[dict[str, object]] = field(default_factory=list)


def _section_words(body: str) -> int:
    return word_count(ANY_CLAIM_MARKER.sub("", body))


def _length_instructions(draft: StoredDraft, budget: int) -> list[dict[str, object]]:
    """Scale every section by the same factor so the page lands on its budget."""
    counts = {s.section_id: _section_words(s.body) for s in draft.draft.sections}
    total = sum(counts.values())
    even = budget / len(counts)
    instructions: list[dict[str, object]] = []
    for section_id, words in counts.items():
        target = max(MIN_SECTION_WORDS, round(words * budget / total if total else even))
        verb = "Expand" if target > words else "Trim"
        instructions.append(
            {
                "code": "WORD_BUDGET",
                "section_id": section_id,
                "message": f"{verb} this section from {words} to about {target} words.",
                "target_words": target,
                "suggested_repair": (
                    "Add depth (examples, steps, specifics) without new company claims."
                    if verb == "Expand"
                    else "Cut repetition and filler; keep every claim marker and planned link."
                ),
            }
        )
    return instructions


def repair_plan(
    report: QAReport | None, draft: StoredDraft | None, word_budget: int | None
) -> RepairPlan | None:
    """The repair a failed report allows, or None when no draft change can fix its errors.

    Section errors rewrite their section; a direct-answer error rewrites the answer; a
    page-length error rewrites every section toward the budget. Anything else (e.g. the
    outline or claims changed) needs a Strategy or outline change, not a repair.
    """
    if report is None or draft is None:
        return None
    errors = [f for f in report.findings if f.severity == "error"]
    targets = {f.section_id for f in errors if f.section_id}
    fix_answer = any(f.section_id is None and "DIRECT_ANSWER" in f.code for f in errors)
    instructions: list[dict[str, object]] = []
    if word_budget and any(f.code == "WORD_BUDGET" for f in errors):
        instructions = _length_instructions(draft, word_budget)
        targets |= {s.section_id for s in draft.draft.sections}
    if not targets and not fix_answer:
        return None
    order = [s.section_id for s in draft.draft.sections]
    return RepairPlan(
        targets=sorted(targets, key=lambda sid: order.index(sid) if sid in order else len(order)),
        fix_direct_answer=fix_answer,
        instructions=instructions,
    )


def g2_blockers(
    card: ContentCard,
    report: QAReport | None,
    draft: StoredDraft | None,
    bundle: BundleStatus | None,
    *,
    warnings_require_dismissal: bool,
) -> list[str]:
    """Why G2 cannot pass right now; empty means it can."""
    blockers: list[str] = []
    if ContentCardState(card.state) != ContentCardState.QA_PASSED:
        blockers.append("QA has not passed.")
    if not qa_is_current(card, report, draft):
        blockers.append("The QA report is stale; run QA again.")
    elif report is not None and report.status != "passed":
        blockers.append("The QA report has blocking errors.")
    if bundle is None or not bundle.is_current:
        blockers.append("The bundle is out of date; rebuild it and run QA again.")
    elif report is not None and report.bundle_hash != bundle.content_hash:
        blockers.append("QA ran against an older bundle; run QA again.")
    if warnings_require_dismissal and report is not None and report.undismissed_warnings():
        blockers.append("Dismiss or fix every warning first.")
    return blockers


def g2_status(card: ContentCard, history: list[GateDecision]) -> G2Status:
    state = ContentCardState(card.state)
    if state in (ContentCardState.APPROVED, ContentCardState.LIVE):
        return "approved"
    if state == ContentCardState.QA_PASSED:
        return "awaiting_review"
    last = next((d for d in history if d.gate == "G2"), None)
    if last is not None and last.action == "send_back" and state in QA_STATES:
        return "sent_back"
    return "not_ready"
