"""V3 Canvas domain Pydantic v2 schemas.

V3 Reference: seo-geo-system-handoff-v3.md §3.1, §9.2

These schemas serve as typed contracts for:
- Canvas anchors
- Workspace configuration (V3 §9.2)
- Claim market overrides
- Scoring configuration
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClaimRow(StrEnum):
    """V3 §3.1: Valid row types for a Claim cell."""

    SUB_PROBLEM = "sub_problem"
    PILLAR = "pillar"
    CAPABILITY = "capability"
    FEATURE = "feature"
    BENEFIT = "benefit"
    PROBLEM_SUMMARY = "problem_summary"
    DIFFERENTIATION_SUMMARY = "differentiation_summary"
    PITCH = "pitch"


class CanvasAnchor(BaseModel):
    """V3 §3.1: Canvas anchor — {text, primary}.

    Anchors marked primary must each pass the stands-on-its-own rule.
    """

    text: str = ""
    primary: bool = False


class MarketConfig(BaseModel):
    """V3 §9.2: Market configuration entry."""

    lang: str = Field(..., min_length=2, max_length=10, description="Language code, e.g. 'en'")
    country: str = Field(..., min_length=2, max_length=2, description="ISO country code, e.g. 'GB'")
    spelling: str = Field(default="", description="Spelling variant, e.g. 'en-GB'")
    currency: str = Field(default="", max_length=3, description="Currency code, e.g. 'GBP'")


class FunnelWeights(BaseModel):
    """V3 §9.2: Funnel weights for scoring."""

    bofu: float = Field(default=1.0, ge=0.0, le=1.0)
    mofu: float = Field(default=0.7, ge=0.0, le=1.0)
    tofu: float = Field(default=0.4, ge=0.0, le=1.0)


class ScoringConfig(BaseModel):
    """V3 §9.2: Keyword scoring weights.

    Score = w_volume x norm(volume) + w_gap x competitor_gap + w_funnel x funnel_weight[funnel]
    """

    w_volume: float = Field(default=0.5, ge=0.0, le=1.0)
    w_gap: float = Field(default=0.3, ge=0.0, le=1.0)
    w_funnel: float = Field(default=0.2, ge=0.0, le=1.0)
    funnel_weight: FunnelWeights = Field(default_factory=FunnelWeights)


class PromptScoringConfig(BaseModel):
    """V3 §9.2: Prompt scoring weights.

    Score = citation_gap x platforms (x platform_weight)
    """

    platform_weight: float = Field(default=1.0, ge=0.0)


class WordBudgets(BaseModel):
    """V3 §9.2: Word budgets by card kind."""

    pillar: int = Field(default=2000, ge=0)
    cluster: int = Field(default=1000, ge=0)
    compare: int = Field(default=1000, ge=0)
    refresh: str = Field(default="inherit", description="'inherit' means use existing page length")
    tables_excluded: bool = Field(default=True)


class AutoApproveGateConfig(BaseModel):
    """V3 §5.4: Gate auto-approval configuration."""

    enabled: bool = False
    kinds: list[str] = Field(default_factory=list)
    after_approvals: int = Field(default=20, ge=0)
    max_send_back_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class AutoApproveConfig(BaseModel):
    """V3 §5.4: Auto-approval configuration for G1 and G2."""

    G1: AutoApproveGateConfig = Field(default_factory=lambda: AutoApproveGateConfig(enabled=True))
    G2: AutoApproveGateConfig = Field(default_factory=AutoApproveGateConfig)


class DigestConfig(BaseModel):
    """V3 §9.2: Digest delivery configuration."""

    day: str = Field(default="Monday")
    recipients: list[str] = Field(default_factory=list)


class StrikingDistanceConfig(BaseModel):
    """V3 §9.2: Striking distance configuration for GSC queries."""

    position_min: int = Field(default=4, ge=1)
    position_max: int = Field(default=15, ge=1)
    impressions_floor: int = Field(default=100, ge=0)


class TechSEOScoreWeights(BaseModel):
    """V3 §9.2: Technical SEO score weights."""

    severe: int = Field(default=5, ge=0)
    moderate: int = Field(default=2, ge=0)
    minor: int = Field(default=1, ge=0)


class ModelConfig(BaseModel):
    """V3 §9.2: Model configuration."""

    default: str = Field(default="", description="Default vendor/model identifier")
    per_stage: dict[str, str] = Field(default_factory=dict, description="Per-stage model overrides")
    translation_provider: str = Field(default="", description="Translation provider identifier")


def _default_reviewers() -> dict[str, list[str]]:
    return {"G1": [], "G2": []}


class WorkspaceConfig(BaseModel):
    """V3 §9.2: Complete workspace configuration.

    This is the typed schema for the workspace_config JSONB column on Project.
    Every field has a sensible default so an empty {} is valid.
    """

    domain: str = Field(default="", description="Workspace domain, e.g. 'example.com'")
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    prompt_scoring: PromptScoringConfig = Field(default_factory=PromptScoringConfig)
    funnel_definitions: dict[str, str] = Field(
        default_factory=lambda: {"bofu": "", "mofu": "", "tofu": ""},
        description="Human-readable funnel stage definitions",
    )
    word_budgets: WordBudgets = Field(default_factory=WordBudgets)
    markets: list[MarketConfig] = Field(default_factory=list)
    demand_strings_exempt_from_spelling: bool = Field(default=True)
    banned_words: list[str] = Field(default_factory=list)
    competitor_stances: dict[str, str] = Field(
        default_factory=dict,
        description="Competitor name → stance mapping",
    )
    reviewers: dict[str, list[str]] = Field(
        default_factory=_default_reviewers,
        description="Gate → list of reviewer identifiers",
    )
    auto_approve: AutoApproveConfig = Field(default_factory=AutoApproveConfig)
    soft_warnings_require_dismissal: bool = Field(default=True)
    digest: DigestConfig = Field(default_factory=DigestConfig)
    experiment_window_days: int = Field(default=28, ge=1)
    striking_distance: StrikingDistanceConfig = Field(default_factory=StrikingDistanceConfig)
    dedupe_similarity_threshold: float = Field(default=0.86, ge=0.0, le=1.0)
    cluster_volume_floor: int = Field(default=50, ge=0)
    techseo_score_weights: TechSEOScoreWeights = Field(default_factory=TechSEOScoreWeights)
    classification_cache: bool = Field(default=True)
    models: ModelConfig = Field(default_factory=ModelConfig)
    monthly_cost_cap_usd: float | None = Field(
        default=None, ge=0.0, description="Per-tenant monthly model cost cap in USD"
    )


class ClaimMarketOverride(BaseModel):
    """Per-market override for a claim — V3 §5.5."""

    text: str = ""
    evidence: str = ""
    excluded: bool = False


# API-facing schemas


class CanvasListItem(BaseModel):
    id: UUID
    product_line: str | None
    name: str
    argument_count: int


class CanvasListResponse(BaseModel):
    company_canvas: CanvasListItem | None
    product_lines: list[CanvasListItem]


class ClaimResponse(BaseModel):
    id: UUID
    row: str
    text: str
    evidence: str
    approved: bool
    approved_by: UUID | None
    version: int
    superseded_by: UUID | None
    market_overrides: dict[str, ClaimMarketOverride]
    inherited: bool = False
    clm_number: str = ""
    model_config = ConfigDict(from_attributes=True)


class ArgumentResponse(BaseModel):
    id: UUID
    order: int
    sub_problem: str | None
    differentiation_pillar: str | None
    capability: str | None
    features: list[str]
    benefit: str | None
    claims: list[ClaimResponse]
    inherited: bool = False
    override: bool = False
    model_config = ConfigDict(from_attributes=True)


class CanvasFullResponse(BaseModel):
    id: UUID
    product_line: str | None
    name: str
    anchors: list[CanvasAnchor]
    problem_summary: str | None
    differentiation_summary: str | None
    version: int
    arguments: list[ArgumentResponse]
    pitch_claim: ClaimResponse | None
    model_config = ConfigDict(from_attributes=True)


class ClaimEditCheckResponse(BaseModel):
    citation_count: int
    claim_text: str
    claim_id: UUID


class ClaimEditConfirmRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    evidence: str = Field(default="", max_length=10_000)


class ClaimEditConfirmResponse(BaseModel):
    old_claim_id: UUID
    new_claim_id: UUID
    new_version: int
    job_run_id: UUID


class PitchGenerateResponse(BaseModel):
    claim: ClaimResponse
    job_run_id: UUID


class PageMetadata(BaseModel):
    total_count: int
    page: int
    page_size: int


class DemandNodeStub(BaseModel):
    id: UUID
    text: str
    type: str
    origin: str
    status: str
    score: float | None = None
    volume: int | None = None
    citation_gap: float | None = None


class ContentCardStub(BaseModel):
    id: UUID
    title: str
    kind: str
    state: str


class DrilldownResponse(BaseModel):
    argument_chain: list[ClaimResponse]
    demand_nodes: list[DemandNodeStub]
    content_cards: list[ContentCardStub]
