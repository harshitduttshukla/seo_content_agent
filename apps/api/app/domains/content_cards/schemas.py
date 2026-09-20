"""V3 Content Cards domain Pydantic v2 schemas.

V3 Reference: seo-geo-system-handoff-v3.md §3.1, §5.1, §5.2, §5.5
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field


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
