"""V3 Demand domain Pydantic v2 schemas.

V3 Reference: seo-geo-system-handoff-v3.md §3.1, §4.5, §4.7
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DemandNodeType(StrEnum):
    """V3 §3.1: A demand node is either a keyword or a prompt."""

    KEYWORD = "keyword"
    PROMPT = "prompt"


class DemandNodeStatus(StrEnum):
    """V3 §4.5: Status in the review pipeline."""

    PENDING = "pending"
    KEPT = "kept"
    DISCARDED = "discarded"
    PENDING_CLASSIFY = "pending_classify"


class DemandNodeOrigin(StrEnum):
    """V3 §3.1: How a demand node was created."""

    UPLOAD = "upload"
    GSC_STRIKING_DISTANCE = "gsc_striking_distance"
    INSIGHT = "insight"


class DemandNodeFunnel(StrEnum):
    """V3 §4.5: Funnel stages (lowercase per V3 convention)."""

    TOFU = "tofu"
    MOFU = "mofu"
    BOFU = "bofu"


class KeywordScoreBreakdown(BaseModel):
    """V3 §4.5: Keyword scoring breakdown.

    Score = w_v x norm(volume) + w_g x competitor_gap + w_f x funnel_weight[funnel]
    """

    volume_component: float = Field(default=0.0, ge=0.0)
    gap_component: float = Field(default=0.0, ge=0.0)
    funnel_component: float = Field(default=0.0, ge=0.0)


class PromptScoreBreakdown(BaseModel):
    """V3 §4.7: Prompt scoring breakdown.

    Score = citation_gap x platforms
    """

    citation_gap: float = Field(default=0.0, ge=0.0, le=1.0)
    platform_count: int = Field(default=0, ge=0)


# API-facing schemas


class DemandNodeResponse(BaseModel):
    id: UUID
    text: str
    type: DemandNodeType
    origin: DemandNodeOrigin
    volume: int | None
    country: str | None
    area_id: UUID | None
    argument_id: UUID | None
    funnel: DemandNodeFunnel | None
    intent: str | None
    status: DemandNodeStatus
    score: float | None
    confidence: float | None
    score_breakdown: KeywordScoreBreakdown | PromptScoreBreakdown | None
    discard_reason: str | None
    citation_gap: float | None
    platforms: list[str]
    competitor_ids: list[UUID]
    competitor_names: list[str]
    variants: list[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DemandSummaryCounts(BaseModel):
    total_discarded: int
    below_065_confidence: int
    total_kept: int
    gsc_striking_distance_count: int


class PageMetadata(BaseModel):
    total_count: int
    page: int
    page_size: int


class DemandNodeListResponse(BaseModel):
    items: list[DemandNodeResponse]
    summary: DemandSummaryCounts
    meta: PageMetadata


class BulkActionRequest(BaseModel):
    ids: list[UUID]
    action: Literal["keep", "discard", "reassign_area", "set_argument"]
    area_id: UUID | None = None
    argument_id: UUID | None = None


class BulkActionResponse(BaseModel):
    updated_count: int
    job_run_id: UUID


class BulkUpdateResponse(BaseModel):
    updated_count: int
    job_run_id: UUID


class PendingClassifyRequest(BaseModel):
    node_ids: list[UUID] = Field(min_length=1, max_length=500)


class DemandReassignRequest(BaseModel):
    node_ids: list[UUID] = Field(min_length=1, max_length=500)
    area_id: UUID


class DemandImportItem(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    type: DemandNodeType
    volume: int | None = Field(default=None, ge=0)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    # A CSV may use an existing area's UUID or its exact project-scoped name.
    area: str | None = Field(default=None, max_length=500)
    funnel: DemandNodeFunnel | None = None
    origin: DemandNodeOrigin = DemandNodeOrigin.UPLOAD
    competitor: str | None = Field(default=None, max_length=500)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    score: float | None = None
    status: DemandNodeStatus = DemandNodeStatus.PENDING


class DemandImportRequest(BaseModel):
    items: list[DemandImportItem] = Field(min_length=1, max_length=2_000)


class DemandImportResponse(BaseModel):
    created_count: int
    existing_count: int
    job_run_id: UUID


# ── Plan (V3 §4.5) ────────────────────────────────────────────────────


class PlanRequest(BaseModel):
    """The selected demand nodes. Preview and confirm take the same body."""

    node_ids: list[UUID] = Field(min_length=1, max_length=500)


class PlanSkippedNode(BaseModel):
    node_id: UUID
    text: str | None
    reason: str


class PlanSecondaryDemand(BaseModel):
    node_id: UUID
    text: str


class PlanCardPreview(BaseModel):
    kind: Literal["pillar", "cluster", "compare", "refresh"]
    primary_node_id: UUID
    primary_text: str
    primary_type: Literal["keyword", "prompt"]
    score: float | None
    volume: int | None
    word_budget: int
    secondary_demands: list[PlanSecondaryDemand] = Field(default_factory=list)


class PlanKindCounts(BaseModel):
    pillar: int = 0
    cluster: int = 0
    compare: int = 0
    refresh: int = 0
    secondary_demands: int = 0


class PlanGroupPreview(BaseModel):
    """One area x market planning group."""

    area_id: UUID
    area_name: str
    market_country: str | None
    counts: PlanKindCounts
    cards: list[PlanCardPreview]


class PlanPreviewResponse(BaseModel):
    selected_count: int
    eligible_count: int
    skipped_count: int
    totals: PlanKindCounts
    groups: list[PlanGroupPreview]
    skipped: list[PlanSkippedNode]
    deferred: list[str]


class PlanResultResponse(PlanPreviewResponse):
    """What confirm wrote: the same shape as the preview plus the new rows."""

    created_count: int
    created_card_ids: list[UUID]
    job_run_id: UUID
