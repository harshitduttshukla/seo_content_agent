"""V3 Content Cards domain Pydantic v2 schemas.

V3 Reference: seo-geo-system-handoff-v3.md §3.1, §5.1, §5.2, §5.5
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class ContentCardKind(StrEnum):
    """V3 §3.1: Content card kinds."""

    PILLAR = "pillar"
    CLUSTER = "cluster"
    COMPARE = "compare"
    REFRESH = "refresh"


class ContentCardState(StrEnum):
    """V3 §5.2: Content card production states.

    State machine:
        backlog → planned → bundled → outlined → [G1] → drafting ⇄ qa_failed
        → qa_passed → [G2] → approved → live

    G1 send-back → outlined (with FEEDBACK)
    G2 send-back → drafting (with FEEDBACK)
    live → refresh card opens at bundled (via stale claim or accepted insight)
    """

    BACKLOG = "backlog"
    PLANNED = "planned"
    BUNDLED = "bundled"
    OUTLINED = "outlined"
    DRAFTING = "drafting"
    QA_FAILED = "qa_failed"
    QA_PASSED = "qa_passed"
    APPROVED = "approved"
    LIVE = "live"


class ContentCardOrigin(StrEnum):
    """V3 §3.1: How a content card was created."""

    PLAN = "plan"
    IMPORT = "import"
    INSIGHT = "insight"
    MANUAL = "manual"


class Market(BaseModel):
    """V3 §5.5: Market identification on a ContentCard."""

    lang: str = Field(default="en", min_length=2, max_length=10)
    country: str = Field(default="US", min_length=2, max_length=2)


# ──────────────────────────────────────────────────────────────────
# State Machine: Valid Transitions
# ──────────────────────────────────────────────────────────────────
# Documented here for reference and future enforcement.
# Full transition service is NOT implemented in Step 0.

VALID_STATE_TRANSITIONS: dict[ContentCardState, list[ContentCardState]] = {
    ContentCardState.BACKLOG: [ContentCardState.PLANNED],
    ContentCardState.PLANNED: [ContentCardState.BUNDLED, ContentCardState.BACKLOG],
    ContentCardState.BUNDLED: [ContentCardState.OUTLINED],
    ContentCardState.OUTLINED: [ContentCardState.DRAFTING],  # G1 pass
    # G1 send-back: remains at OUTLINED with FEEDBACK
    ContentCardState.DRAFTING: [ContentCardState.QA_FAILED, ContentCardState.QA_PASSED],
    ContentCardState.QA_FAILED: [ContentCardState.DRAFTING],  # repair cycle
    ContentCardState.QA_PASSED: [ContentCardState.APPROVED],  # G2 pass
    # G2 send-back: → DRAFTING with FEEDBACK
    ContentCardState.APPROVED: [ContentCardState.LIVE],
    ContentCardState.LIVE: [],  # terminal; refresh creates a new card at BUNDLED
}

# States that are terminal (no forward transitions from this card).
TERMINAL_STATES: frozenset[ContentCardState] = frozenset({ContentCardState.LIVE})

# States that are non-terminal.
NON_TERMINAL_STATES: frozenset[ContentCardState] = frozenset(
    s for s in ContentCardState if s not in TERMINAL_STATES
)


# API-facing schemas


class SiteImportRequest(BaseModel):
    url: AnyHttpUrl
    website_id: UUID | None = None
    force_refresh: bool = False


class SiteImportResponse(BaseModel):
    job_run_id: UUID
    status: str
    created_count: int
    existing_count: int


class SiteImportStatusResponse(BaseModel):
    job_run_id: UUID
    status: str
    created_at: datetime
    completed_at: datetime | None
    created_count: int
    existing_count: int
    unmapped_count: int


class ContentCardImportResult(BaseModel):
    url: str
    content_card_id: UUID | None
    status: str
    error: str | None = None


# Content Hub plan board (V3 §5.1)


class BoardRef(BaseModel):
    """A named reference shown on the card face (area, argument, owner)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str


class BoardDemandRef(BaseModel):
    """The card's primary keyword or prompt, with what the face shows for it."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    text: str
    volume: int | None = None
    citation_gap: float | None = None
    platform_count: int = 0


class BoardCard(BaseModel):
    """One card as the board renders it. Read-only projection; no ORM object."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    kind: str
    state: str
    column: str
    origin: str
    area: BoardRef | None
    argument: BoardRef | None
    owner: BoardRef | None
    market: str | None
    due: date | None
    priority: int
    primary_demand: BoardDemandRef | None
    primary_prompt: BoardDemandRef | None
    secondary_demand_count: int
    # The primary demand's score, else the primary prompt's; None when unscored.
    score: float | None
    has_qa_report: bool
    url: str | None
    cms_id: str | None
    published_at: datetime | None
    stale_claim_count: int
    planned_at: datetime | None
    # §5.1 "new" chip: entered Planned strictly after the plan lock. Server-derived.
    is_new_after_plan_lock: bool
    revision: int
    updated_at: datetime


class BoardColumnView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    tone: Literal["rest", "system", "human"]
    count: int
    cards: list[BoardCard]


class BoardFilterOptions(BaseModel):
    """Values present on this project's cards, for the filter row."""

    model_config = ConfigDict(extra="forbid")

    areas: list[BoardRef]
    kinds: list[str]
    owners: list[BoardRef]
    arguments: list[BoardRef]
    markets: list[str]


class ContentHubBoard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    plan_locked_at: datetime | None
    total_count: int
    columns: list[BoardColumnView]
    filter_options: BoardFilterOptions


class BoardFilters(BaseModel):
    """Allowlisted board filters; all optional and combined with AND."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    area_id: UUID | None = None
    kind: ContentCardKind | None = None
    owner_id: UUID | None = None
    argument_id: UUID | None = None
    market: str | None = Field(default=None, pattern=r"^[a-z]{2,10}-[A-Z]{2}$")


class BoardMoveRequest(BaseModel):
    """Backlog ↔ Planned only. ``revision`` is the card revision the client saw."""

    model_config = ConfigDict(extra="forbid")

    target_state: Literal["backlog", "planned"]
    revision: int = Field(ge=1)


class PlannedOrderRequest(BaseModel):
    """The full Planned column, top first. Must match the server's set exactly."""

    model_config = ConfigDict(extra="forbid")

    card_ids: list[UUID] = Field(min_length=1, max_length=1000)
