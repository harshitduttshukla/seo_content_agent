"""API contracts for the V3 card detail, Bundle → Outline, G1 and Draft workflow (§5.1-5.3, §6)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from app.domains.ai.context import CardContextBundle
from app.domains.content_cards.draft import StoredDraft
from app.domains.content_cards.outline import OutlineIssue, OutlineV3
from app.domains.content_cards.schemas import BoardCard
from pydantic import BaseModel, ConfigDict, Field, field_validator


class BundleStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_ref: UUID
    content_hash: str
    built_at: datetime
    # False when the stored bundle no longer matches what the sources would give now.
    is_current: bool


class ClaimOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    text: str
    evidence: str
    row: str
    argument_id: UUID | None
    argument_name: str | None
    version: int
    approved: bool


class CardCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    status: Literal["pass", "fail", "not_applicable"]
    detail: str = ""


class CardActions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_build_bundle: bool
    can_generate_outline: bool
    can_save_outline: bool
    # G1: the card is outlined, every check passes and the viewer may review.
    can_review_g1: bool = False
    can_generate_draft: bool = False


# ── G1 outline review (handoff §5.2-5.3, §6.3) ────────────────────────

# "This is about", as in the writer view's send-back form.
G1Reason = Literal["writer", "claim", "tone_rule", "plan"]
G1Status = Literal["not_ready", "awaiting_review", "sent_back", "approved"]


class GateDecision(BaseModel):
    """One recorded gate decision (a ``v3_gate_decision`` JobRun)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    gate: Literal["G1"]
    action: Literal["approve", "send_back"]
    reviewer_id: UUID | None
    reviewer_name: str | None
    decided_at: datetime
    # The card revision the reviewer saw when deciding.
    card_revision: int
    reason: G1Reason | None = None
    feedback: str | None = None


class G1Review(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: G1Status
    # Every G1 check passes (bundle current, outline valid and grounded).
    ready: bool
    # The viewer holds content.review and, when configured, is a named G1 reviewer.
    can_review: bool
    # workspace_config.reviewers.G1 names specific reviewers.
    reviewers_restricted: bool
    last_decision: GateDecision | None
    history: list[GateDecision]


class G1ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)


class G1SendBackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)
    reason: G1Reason
    feedback: str = Field(max_length=4000)

    @field_validator("feedback")
    @classmethod
    def _required(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("feedback is required to send an outline back")
        return text


class G1DecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card: BoardCard
    decision: GateDecision


# ── Draft (handoff §6.3, §6.8 call 2) ─────────────────────────────────


class DraftRunStatus(BaseModel):
    """The latest ``v3_draft_generation`` JobRun, so failures stay visible."""

    model_config = ConfigDict(extra="forbid")

    job_run_id: UUID
    status: str
    prompt_version: str
    provider: str
    model: str
    attempts: int
    error: str | None
    issues: list[OutlineIssue]
    created_at: datetime
    stored: bool


class DraftGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)
    model: str | None = Field(default=None, max_length=128)


class DraftGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card: BoardCard
    draft: StoredDraft


class CardDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card: BoardCard
    outline: OutlineV3 | None
    # A stored outline that no longer parses is reported, not silently dropped.
    outline_unreadable: bool
    bundle: BundleStatus | None
    # The context the next bundle would contain, from current project data.
    context: CardContextBundle
    claim_options: list[ClaimOption]
    checks: list[CardCheck]
    actions: CardActions
    review: G1Review
    draft: StoredDraft | None = None
    # A stored draft that no longer parses is reported, not silently dropped.
    draft_unreadable: bool = False
    last_draft_run: DraftRunStatus | None = None


class BundleBuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)


class BundleBuildResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card: BoardCard
    bundle: BundleStatus
    reused: bool


class OutlineGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str | None = Field(default=None, max_length=128)


class OutlineProposal(BaseModel):
    """A validated outline for the human to review; the card is not changed."""

    model_config = ConfigDict(extra="forbid")

    outline: OutlineV3
    job_run_id: UUID
    prompt_version: str
    provider: str
    model: str
    attempts: int
    bundle_ref: UUID


class OutlineSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outline: OutlineV3
    revision: int = Field(ge=1)


class OutlineSaveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card: BoardCard
    outline: OutlineV3
