"""Structured Pydantic schemas for Content Agent Context.

This module defines the pure, truthful data contracts returned by the
Content Agent Context Builder. No presentation defaults or fabricated facts
are injected here; missing database values are represented strictly as
None or empty collections.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RequestContext(BaseModel):
    """Information about the current content task/request."""

    model_config = ConfigDict(extra="ignore")

    task_type: str = Field(
        default="content_edit",
        description="Task identifier (e.g. content_edit, article_generation)",
    )
    user_message: str = Field(default="", description="User prompt or instruction")
    document_id: UUID = Field(description="Target ContentDocument ID")
    project_id: UUID = Field(description="Target Project ID")
    organization_id: UUID = Field(description="Target Organization ID")
    website_id: UUID | None = Field(default=None, description="Target Website ID if associated")
    selected_block_id: str | None = Field(default=None, description="Focused block ID in editor")
    selected_text: str | None = Field(default=None, description="Highlighted text slice")
    full_document_request: bool = Field(
        default=False, description="Whether full-document expansion is requested"
    )
    requested_at: datetime = Field(description="UTC timestamp of the request")


class ProjectContext(BaseModel):
    """Tenant-authorized project identity."""

    model_config = ConfigDict(extra="ignore")

    project_id: UUID
    organization_id: UUID
    name: str | None = None
    slug: str | None = None


class WebsiteContext(BaseModel):
    """Project-owned website identity."""

    model_config = ConfigDict(extra="ignore")

    website_id: UUID | None = None
    name: str | None = None
    base_url: str | None = None
    normalized_host: str | None = None
    locale: str | None = None
    country: str | None = None
    settings: dict[str, object] = Field(default_factory=dict)


class SEOStrategyContext(BaseModel):
    """Active SEO Strategy context loaded from the project's current version."""

    model_config = ConfigDict(extra="ignore")

    strategy_id: UUID | None = None
    version: int | None = None
    status: str | None = None
    business_name: str | None = None
    business_description: str | None = None
    industry: str | None = None
    locations: list[str] = Field(default_factory=list)
    audience_segments: list[str] = Field(default_factory=list)
    audience_personas: list[dict[str, object]] = Field(default_factory=list)
    audience_needs: list[str] = Field(default_factory=list)
    buying_stages: list[str] = Field(default_factory=list)
    products: list[dict[str, object]] = Field(default_factory=list)
    services: list[dict[str, object]] = Field(default_factory=list)
    markets: list[dict[str, object]] = Field(default_factory=list)
    goals: list[dict[str, object]] = Field(default_factory=list)
    competitors: list[dict[str, object]] = Field(default_factory=list)
    seo_objectives: list[str] = Field(default_factory=list)
    content_objectives: list[str] = Field(default_factory=list)
    priority_topics: list[str] = Field(default_factory=list)


class KeywordItemContext(BaseModel):
    """Details for a specific keyword in inventory."""

    model_config = ConfigDict(extra="ignore")

    keyword_id: UUID | None = None
    keyword: str
    normalized_keyword: str | None = None
    search_volume: int | None = None
    keyword_difficulty: float | None = None
    cpc: float | None = None
    intent: str | None = None
    intent_confidence: float | None = None
    funnel_stage: str | None = None
    source: str | None = None
    role: str = "primary"  # primary, secondary, related


class KeywordContext(BaseModel):
    """Relevant keyword inventory context for the content task."""

    model_config = ConfigDict(extra="ignore")

    primary_keyword: KeywordItemContext | None = None
    secondary_keywords: list[KeywordItemContext] = Field(default_factory=list)
    cluster_id: UUID | None = None
    cluster_name: str | None = None
    cluster_score: float | None = None
    cluster_keywords: list[str] = Field(default_factory=list)


class ContentMapContext(BaseModel):
    """Content Map Information Architecture subgraph for the planned page."""

    model_config = ConfigDict(extra="ignore")

    page_id: UUID | None = None
    page_title: str | None = None
    page_slug: str | None = None
    page_url: str | None = None
    content_type: str | None = None
    page_status: str | None = None
    pillar_id: UUID | None = None
    pillar_name: str | None = None
    pillar_slug: str | None = None
    pillar_description: str | None = None
    topic_id: UUID | None = None
    topic_name: str | None = None
    topic_slug: str | None = None
    topic_description: str | None = None
    cluster_id: UUID | None = None
    cluster_name: str | None = None
    parent_page_id: UUID | None = None
    parent_page_title: str | None = None
    sibling_pages: list[dict[str, object]] = Field(default_factory=list)
    graph_nodes: list[dict[str, object]] = Field(default_factory=list)
    graph_edges: list[dict[str, object]] = Field(default_factory=list)


class SEOGuideContext(BaseModel):
    """SEO Guide specifications, SERP notes, and deterministic rules."""

    model_config = ConfigDict(extra="ignore")

    guide_id: UUID | None = None
    version: int | None = None
    status: str | None = None
    primary_keyword: str | None = None
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str | None = None
    target_audience: str | None = None
    recommended_title: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    recommended_url: str | None = None
    content_type: str | None = None
    word_count_target: int | None = None
    required_topics: list[str] = Field(default_factory=list)
    key_entities: list[str] = Field(default_factory=list)
    serp_notes: str | None = None
    content_requirements: list[str] = Field(default_factory=list)
    outline: list[dict[str, object]] = Field(default_factory=list)
    seo_rules: dict[str, object] = Field(default_factory=dict)


class ContentBriefContext(BaseModel):
    """Complete Content Brief parameters and requirements."""

    model_config = ConfigDict(extra="ignore")

    brief_id: UUID | None = None
    version: int | None = None
    status: str | None = None
    title: str | None = None
    primary_keyword: str | None = None
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str | None = None
    target_audience: str | None = None
    business_goal: str | None = None
    content_type: str | None = None
    recommended_title: str | None = None
    recommended_url: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    target_word_count: int | None = None
    required_topics: list[str] = Field(default_factory=list)
    key_entities: list[str] = Field(default_factory=list)
    questions_to_answer: list[str] = Field(default_factory=list)
    internal_link_targets: list[dict[str, object]] = Field(default_factory=list)
    external_source_requirements: list[str] = Field(default_factory=list)
    content_requirements: list[str] = Field(default_factory=list)
    brand_requirements: dict[str, object] = Field(default_factory=dict)


class BrandRulesContext(BaseModel):
    """Tone, voice, style, forbidden words, and formatting rules."""

    model_config = ConfigDict(extra="ignore")

    tone: str | None = None
    voice: str | None = None
    style: str | None = None
    words_to_avoid: list[str] = Field(default_factory=list)
    formatting_rules: list[str] = Field(default_factory=list)


class InternalLinkingContext(BaseModel):
    """Approved link targets, link opportunities, and page relationships."""

    model_config = ConfigDict(extra="ignore")

    approved_targets: list[dict[str, object]] = Field(default_factory=list)
    opportunities: list[dict[str, object]] = Field(default_factory=list)
    relationships: list[dict[str, object]] = Field(default_factory=list)


class CrawledPageEvidence(BaseModel):
    """Structured, bounded crawl evidence for an existing page."""

    model_config = ConfigDict(extra="ignore")

    page_id: UUID | None = None
    url: str
    title: str | None = None
    meta_description: str | None = None
    headings: list[str] = Field(default_factory=list)
    content_snippet: str | None = None
    word_count: int = 0
    content_status: str | None = None


class WebsiteCrawlContext(BaseModel):
    """Relevant stored website crawl context."""

    model_config = ConfigDict(extra="ignore")

    website_id: UUID | None = None
    base_url: str | None = None
    crawled_pages: list[CrawledPageEvidence] = Field(default_factory=list)


class ExistingPageEvidence(BaseModel):
    """Relevant existing page evidence (e.g. current page existing version, siblings)."""

    model_config = ConfigDict(extra="ignore")

    page_id: UUID | None = None
    url: str
    title: str | None = None
    meta_description: str | None = None
    relationship: str = "existing_version"  # existing_version, sibling, parent, linked


class ExistingPagesContext(BaseModel):
    """Related existing pages in the project."""

    model_config = ConfigDict(extra="ignore")

    pages: list[ExistingPageEvidence] = Field(default_factory=list)


class CurrentDocumentBlock(BaseModel):
    """A single structured content block in the active document."""

    model_config = ConfigDict(extra="ignore")

    id: str
    type: str = "paragraph"
    text: str = ""
    level: int | None = None
    is_focused: bool = False
    is_adjacent: bool = False


class CurrentDocumentContext(BaseModel):
    """Current ContentDocument state and structured blocks."""

    model_config = ConfigDict(extra="ignore")

    document_id: UUID
    title: str = ""
    slug: str = ""
    current_word_count: int = 0
    document_status: str = "DRAFT"
    current_version: int = 1
    lock_version: int = 1
    blocks: list[CurrentDocumentBlock] = Field(default_factory=list)
    total_block_count: int = 0
    truncated: bool = False
    block_limit: int | None = None
    content_truncation: int | None = None


class SelectionContext(BaseModel):
    """Active user selection in the editor."""

    model_config = ConfigDict(extra="ignore")

    selected_block_id: str | None = None
    selected_text: str | None = None
    selected_block: CurrentDocumentBlock | None = None
    surrounding_blocks: list[CurrentDocumentBlock] = Field(default_factory=list)


class ConversationMessageContext(BaseModel):
    """Structured recent chat message."""

    model_config = ConfigDict(extra="ignore")

    message_id: UUID | None = None
    role: str  # USER, ASSISTANT
    content: str
    created_at: datetime | None = None


class ConversationContext(BaseModel):
    """Recent conversation history."""

    model_config = ConfigDict(extra="ignore")

    messages: list[ConversationMessageContext] = Field(default_factory=list)
    message_count: int = 0


class ContextProvenance(BaseModel):
    """Explicit source tracking for every context section."""

    model_config = ConfigDict(extra="ignore")

    strategy_id: UUID | None = None
    strategy_version: int | None = None
    strategy_source: str | None = None
    brief_id: UUID | None = None
    brief_version: int | None = None
    brief_source: str | None = None
    guide_id: UUID | None = None
    guide_version: int | None = None
    guide_source: str | None = None
    page_id: UUID | None = None
    page_source: str | None = None
    website_id: UUID | None = None
    document_id: UUID
    keyword_ids: list[UUID] = Field(default_factory=list)
    cluster_id: UUID | None = None
    opportunity_ids: list[UUID] = Field(default_factory=list)
    relationship_ids: list[UUID] = Field(default_factory=list)
    crawled_page_ids: list[UUID] = Field(default_factory=list)
    intent_source: str | None = None
    audience_source: str | None = None
    collected_at: datetime


class ContextBudget(BaseModel):
    """Context budget limits, estimations, and truncation observability."""

    model_config = ConfigDict(extra="ignore")

    max_token_budget: int = 8000
    estimated_tokens: int = 0
    truncated: bool = False
    truncated_sections: list[str] = Field(default_factory=list)


class ContentAgentContext(BaseModel):
    """The authoritative, comprehensive structured context for Content Agent operations.

    Consumed by Prompt Builders, Content Agent loops, and the Content Harness.
    Never contains LLM call artifacts or fabricated SEO facts.
    """

    model_config = ConfigDict(extra="ignore")

    request: RequestContext
    project: ProjectContext
    website: WebsiteContext
    seo_strategy: SEOStrategyContext
    keyword_context: KeywordContext
    content_map: ContentMapContext
    seo_guide: SEOGuideContext
    content_brief: ContentBriefContext
    brand_rules: BrandRulesContext
    internal_linking: InternalLinkingContext
    website_context: WebsiteCrawlContext
    existing_pages: ExistingPagesContext
    current_document: CurrentDocumentContext
    selection: SelectionContext
    conversation: ConversationContext

    # Resolved cross-cutting fields with deterministic precedence
    resolved_intent: str | None = None
    resolved_intent_source: str | None = None
    resolved_audience: str | None = None
    resolved_audience_source: str | None = None

    # Normalized collections (deduplicated across Brief & Guide)
    entities: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    content_requirements: list[str] = Field(default_factory=list)
    source_requirements: list[str] = Field(default_factory=list)
    competitors: list[dict[str, object]] = Field(default_factory=list)

    # Provenance and budget metadata
    provenance: ContextProvenance
    budget: ContextBudget


# ──────────────────────────────────────────────────────────────────
# V3 ContentCard context bundle (handoff §6.1)
# ──────────────────────────────────────────────────────────────────
# Assembled by ContentAgentContextBuilder.build_card_bundle from project-scoped
# rows only. Sections are listed in V3 precedence order; the budget trims from
# the last (pitch) towards the first (rules), never the other way round.

BUNDLE_SECTION_PRECEDENCE: tuple[str, ...] = (
    "rules",
    "claims",
    "demand",
    "tone",
    "siblings",
    "references",
    "pitch",
)


class BundleSource(BaseModel):
    """Where one piece of bundle context came from."""

    model_config = ConfigDict(extra="forbid")

    section: str
    source_type: str  # claim, demand_node, brand_kit, social_proof, content_card, ...
    source_id: UUID
    version: int | None = None


class BundleCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    kind: str
    origin: str
    market: str | None
    word_budget: int | None
    url: str | None
    # "prompt" when the card has a primary prompt and no primary keyword.
    primary_mode: str


class BundleRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brand: BrandRulesContext
    # The V3 claim rule every generation must follow; not configurable here.
    claim_policy: str


class BundleClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    text: str
    evidence: str
    row: str
    argument_id: UUID | None
    version: int


class BundleDemand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    role: str  # primary, prompt, secondary
    type: str
    text: str
    volume: int | None = None
    intent: str | None = None
    citation_gap: float | None = None
    platforms: list[str] = Field(default_factory=list)


class BundleTone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tone: str | None
    voice_snippets: list[str] = Field(default_factory=list)
    social_proof: list[str] = Field(default_factory=list)


class BundleSibling(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    kind: str
    state: str
    url: str | None


class BundleReferences(BaseModel):
    """Stored site evidence; the only source of URLs a generation may use."""

    model_config = ConfigDict(extra="forbid")

    existing_pages: ExistingPagesContext = Field(default_factory=ExistingPagesContext)
    website: WebsiteCrawlContext = Field(default_factory=WebsiteCrawlContext)
    internal_linking: InternalLinkingContext = Field(default_factory=InternalLinkingContext)


class BundlePitch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    argument_id: UUID | None = None
    differentiation_pillar: str = ""
    sub_problem: str = ""
    capability: str = ""
    benefit: str = ""
    problem_summary: str = ""
    differentiation_summary: str = ""


class BundleBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_tokens: int
    used_tokens: int
    truncated_sections: list[str] = Field(default_factory=list)


class CardContextBundle(BaseModel):
    """What exactly the model is given for one ContentCard. Deterministic."""

    model_config = ConfigDict(extra="forbid")

    card: BundleCard
    rules: BundleRules
    claims: list[BundleClaim]
    demand: list[BundleDemand]
    tone: BundleTone
    siblings: list[BundleSibling]
    references: BundleReferences
    pitch: BundlePitch
    sources: list[BundleSource]
    budget: BundleBudget
