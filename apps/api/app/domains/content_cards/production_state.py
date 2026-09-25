"""Pure read-side rules for V3 QA freshness and G2 readiness (handoff §5.2, §6.4).

One definition shared by the card detail view and the G2/QA write paths, so the UI
and the server never disagree about whether QA is current or G2 may pass.
"""

from app.domains.content_cards.draft import StoredDraft
from app.domains.content_cards.models import ContentCard
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
