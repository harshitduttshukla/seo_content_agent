"""Pydantic schemas for content pages, architecture, and graph projection."""

from datetime import datetime
from uuid import UUID

from app.domains.content.models import (
    ArchitectureStatus,
    MappingType,
    OpportunityStatus,
    PageContentType,
    PageType,
    PlannedPageStatus,
)
from app.domains.keywords.models import SearchIntent
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ContentPageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    website_id: UUID
    url: str
    normalized_url: str
    canonical_url: str | None
    title: str
    http_status: int | None
    content_status: str
    word_count: int
    last_crawled_at: datetime | None
    created_at: datetime


class ContentPageDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    website_id: UUID
    url: str
    normalized_url: str
    canonical_url: str | None
    title: str
    meta_description: str
    language: str
    http_status: int | None
    content_type: str
    word_count: int
    content_hash: str
    content_status: str
    cleaned_content: str
    structured_content: dict[str, object]
    metadata: dict[str, object] = Field(
        default_factory=dict, validation_alias=AliasChoices("metadata_", "metadata")
    )
    headings: list[dict[str, object]] = []
    images: list[dict[str, object]] = []
    first_seen_at: datetime
    last_crawled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ContentPageList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[ContentPageSummary]


class PageLinkDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    website_id: UUID
    source_page_id: UUID
    target_url: str
    normalized_target_url: str
    target_page_id: UUID | None
    anchor_text: str
    rel: str | None
    is_internal: bool
    nofollow: bool
    ugc: bool
    sponsored: bool
    discovered_at: datetime


class PageLinkList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[PageLinkDetail]


class ContentPageVersionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    page_id: UUID
    crawl_job_id: UUID | None
    content_hash: str
    title: str
    created_at: datetime


# --- Content Pillars ---


class ContentPillarCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    slug: str | None = None
    description: str = ""
    business_goal: str = ""
    priority: int = Field(default=1, ge=1)


class ContentPillarUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    slug: str | None = None
    description: str | None = None
    business_goal: str | None = None
    priority: int | None = Field(default=None, ge=1)
    status: ArchitectureStatus | str | None = None


class ContentPillarDetail(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    name: str
    slug: str
    description: str
    business_goal: str
    priority: int
    status: str
    topic_count: int = 0
    created_at: datetime
    updated_at: datetime


class ContentPillarList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[ContentPillarDetail]


# --- Topics ---


class TopicCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    slug: str | None = None
    pillar_id: UUID | None = None
    description: str = ""
    priority: int = Field(default=1, ge=1)


class TopicUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    slug: str | None = None
    pillar_id: UUID | None = None
    description: str | None = None
    priority: int | None = Field(default=None, ge=1)
    status: ArchitectureStatus | str | None = None


class TopicDetail(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    pillar_id: UUID | None = None
    pillar_name: str | None = None
    name: str
    slug: str
    description: str
    priority: int
    status: str
    cluster_count: int = 0
    created_at: datetime
    updated_at: datetime


class TopicList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[TopicDetail]


# --- Keyword to Page Mappings ---


class KeywordPageMappingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword_id: UUID
    page_id: UUID | None = None
    mapping_type: MappingType | str = MappingType.PRIMARY_TARGET
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    rationale: str = ""
    website_id: UUID | None = None


class KeywordPageMappingDetail(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    website_id: UUID
    keyword_id: UUID
    keyword: str
    search_volume: int = 0
    intent: str = ""
    page_id: UUID | None = None
    page_url: str | None = None
    page_title: str | None = None
    mapping_type: str
    confidence: float
    source: str
    status: str
    rationale: str
    created_at: datetime
    updated_at: datetime


class KeywordPageMappingList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[KeywordPageMappingDetail]


class MappingAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_keywords: int
    mapped_count: int
    unmapped_count: int
    new_mappings_created: int
    updated_mappings: int


# --- Keyword Cannibalization ---


class CannibalizationWarningDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    keyword_id: UUID
    keyword: str
    intent: str
    competing_pages: list[dict[str, object]]
    severity: str = "HIGH"
    reason: str


class CannibalizationWarningList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[CannibalizationWarningDetail]


# --- Content Opportunities & Gaps ---


class ContentOpportunityDetail(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    website_id: UUID
    cluster_id: UUID | None = None
    cluster_name: str | None = None
    keyword_id: UUID | None = None
    keyword: str | None = None
    action: str
    priority: float
    business_value_score: float
    existing_page_id: UUID | None = None
    existing_page_url: str | None = None
    reason: str
    confidence: float
    status: str
    created_at: datetime
    updated_at: datetime


class ContentOpportunityList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[ContentOpportunityDetail]


class ContentOpportunityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OpportunityStatus | str


# --- Graph Projection (React Flow Ready) ---


class GraphNodeData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str
    subtitle: str = ""
    status: str = "active"
    metrics: dict[str, object] = Field(default_factory=dict)
    details: dict[str, object] = Field(default_factory=dict)


class ContentArchitectureGraphNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    type: str  # "pillar", "topic", "cluster", "page"
    data: GraphNodeData


class ContentArchitectureGraphEdge(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    source: str
    target: str
    type: str  # "contains", "targets", "supports"
    label: str = ""


class ContentArchitectureGraphResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nodes: list[ContentArchitectureGraphNode]
    edges: list[ContentArchitectureGraphEdge]


# --- Phase 4 Planned Content Pages & Keywords ---


class PlannedContentPageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    slug: str = Field(min_length=1, max_length=200)
    url: str = ""
    page_type: PageType = PageType.PLANNED
    content_type: PageContentType = PageContentType.GUIDE
    status: PlannedPageStatus = PlannedPageStatus.PLANNED
    intent: SearchIntent = SearchIntent.INFORMATIONAL
    primary_keyword: str = ""
    primary_keyword_id: UUID | None = None
    cluster_id: UUID | None = None
    topic_id: UUID | None = None
    pillar_id: UUID | None = None
    priority: int = Field(default=1, ge=1, le=100)
    business_value: float = Field(default=0.0, ge=0.0, le=100.0)
    existing_page_id: UUID | None = None
    website_id: UUID | None = None


class PlannedContentPageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=500)
    slug: str | None = Field(default=None, min_length=1, max_length=200)
    url: str | None = None
    page_type: PageType | None = None
    content_type: PageContentType | None = None
    status: PlannedPageStatus | None = None
    intent: SearchIntent | None = None
    primary_keyword: str | None = None
    primary_keyword_id: UUID | None = None
    cluster_id: UUID | None = None
    topic_id: UUID | None = None
    pillar_id: UUID | None = None
    priority: int | None = Field(default=None, ge=1, le=100)
    business_value: float | None = Field(default=None, ge=0.0, le=100.0)
    existing_page_id: UUID | None = None


class PlannedContentPageDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    website_id: UUID | None = None
    title: str
    slug: str
    url: str
    page_type: str
    content_type: str
    status: str
    intent: str
    primary_keyword: str
    primary_keyword_id: UUID | None = None
    cluster_id: UUID | None = None
    cluster_name: str | None = None
    topic_id: UUID | None = None
    topic_name: str | None = None
    pillar_id: UUID | None = None
    pillar_name: str | None = None
    priority: int
    business_value: float
    existing_page_id: UUID | None = None
    existing_page_url: str | None = None
    secondary_keywords: list[str] = Field(default_factory=list)
    inbound_links_count: int = 0
    outbound_links_count: int = 0
    created_at: datetime
    updated_at: datetime


class PlannedContentPageList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[PlannedContentPageDetail]
    total: int = 0


class PageKeywordAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword_id: UUID
    keyword_role: str = "SECONDARY"


class PageKeywordDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    page_id: UUID
    keyword_id: UUID
    keyword: str = ""
    keyword_role: str
    created_at: datetime


class PageKeywordList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[PageKeywordDetail]


class ConvertOpportunityToPageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    slug: str | None = None
    content_type: PageContentType = PageContentType.GUIDE
    priority: int | None = None
