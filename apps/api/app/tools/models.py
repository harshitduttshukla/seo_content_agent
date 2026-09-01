"""Phase 0 Pydantic contracts for the future governed AI tool catalog.

These models define boundaries only. No executor or business behavior is implemented.
"""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VersionRef(StrictModel):
    resource_id: UUID
    version_id: UUID
    content_hash: str


class ProposedChange(StrictModel):
    proposal_id: UUID
    base_version_id: UUID
    patch: list[dict[str, object]]
    rationale: str
    requires_approval: bool = True


class StrategySnapshot(StrictModel):
    strategy: VersionRef
    structured_data: dict[str, object]
    status: str


class GetStrategyInput(StrictModel):
    project_id: UUID
    version_id: UUID | None = None


class GetStrategyOutput(StrictModel):
    snapshot: StrategySnapshot


class UpdateStrategyInput(StrictModel):
    project_id: UUID
    base_version_id: UUID
    patch: list[dict[str, object]]
    reason: str


class UpdateStrategyOutput(StrictModel):
    proposal: ProposedChange


class KeywordSummary(StrictModel):
    keyword_id: UUID
    keyword: str
    intent: str | None
    cluster_id: UUID | None
    search_volume: int | None = Field(default=None, ge=0)
    priority: int | None = None


class SearchKeywordsInput(StrictModel):
    project_id: UUID
    query: str | None = None
    intent: str | None = None
    cluster_id: UUID | None = None
    limit: int = Field(default=20, ge=1, le=100)


class SearchKeywordsOutput(StrictModel):
    keywords: list[KeywordSummary]
    truncated: bool


class GetKeywordClusterInput(StrictModel):
    project_id: UUID
    cluster_id: UUID


class GetKeywordClusterOutput(StrictModel):
    cluster_id: UUID
    name: str
    intent: str
    keywords: list[KeywordSummary]
    target_page_id: UUID | None
    version: int


class ClassifyIntentInput(StrictModel):
    project_id: UUID
    keyword_ids: list[UUID] = Field(min_length=1, max_length=100)
    taxonomy_version: str


class IntentAssessment(StrictModel):
    keyword_id: UUID
    intent: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]


class ClassifyIntentOutput(StrictModel):
    proposal_id: UUID
    assessments: list[IntentAssessment]


class FindKeywordGapsInput(StrictModel):
    project_id: UUID
    strategy_version_id: UUID
    competitor_ids: list[UUID] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=25, ge=1, le=100)


class KeywordGap(StrictModel):
    query: str
    rationale: str
    estimated_intent: str
    evidence_source_ids: list[UUID]


class FindKeywordGapsOutput(StrictModel):
    gaps: list[KeywordGap]
    method_version: str


class GetContentMapInput(StrictModel):
    project_id: UUID
    statuses: list[str] = Field(default_factory=list)
    max_nodes: int = Field(default=500, ge=1, le=2_000)


class GraphNode(StrictModel):
    node_id: UUID
    node_type: str
    label: str
    metadata: dict[str, object]


class GraphEdge(StrictModel):
    edge_id: UUID
    source_id: UUID
    target_id: UUID
    edge_type: str


class GetContentMapOutput(StrictModel):
    revision: int
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool


class GetRelatedPagesInput(StrictModel):
    project_id: UUID
    page_id: UUID
    relationship_types: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)


class RelatedPage(StrictModel):
    page_id: UUID
    title: str
    relationship_type: str
    score: float = Field(ge=0, le=1)


class GetRelatedPagesOutput(StrictModel):
    pages: list[RelatedPage]


class CreateContentBriefInput(StrictModel):
    project_id: UUID
    page_id: UUID
    strategy_version_id: UUID
    cluster_id: UUID
    instruction: str | None = None


class CreateContentBriefOutput(StrictModel):
    proposal_id: UUID
    brief: dict[str, object]
    dependency_versions: dict[str, str]


class GenerateOutlineInput(StrictModel):
    project_id: UUID
    page_id: UUID
    brief_id: UUID
    brief_version: int


class GenerateOutlineOutput(StrictModel):
    proposal_id: UUID
    outline: list[dict[str, object]]
    coverage_notes: list[str]


class RewriteContentInput(StrictModel):
    project_id: UUID
    page_id: UUID
    base_version_id: UUID
    selected_node_ids: list[str]
    instruction: str


class RewriteContentOutput(StrictModel):
    proposal: ProposedChange
    source_ids: list[UUID]


class GetSeoRulesInput(StrictModel):
    project_id: UUID
    page_id: UUID | None = None
    categories: list[str] = Field(default_factory=list)


class RuleSummary(StrictModel):
    rule_id: UUID
    key: str
    evaluation_type: str
    severity: str
    version: int
    definition: dict[str, object]


class GetSeoRulesOutput(StrictModel):
    rules: list[RuleSummary]
    rule_set_hash: str


class CheckSeoInput(StrictModel):
    project_id: UUID
    page_id: UUID
    content_version_id: UUID
    rule_ids: list[UUID] = Field(default_factory=list)


class Finding(StrictModel):
    code: str
    severity: str
    message: str
    evidence: dict[str, object]
    rule_id: UUID | None = None


class CheckSeoOutput(StrictModel):
    analysis_id: UUID
    deterministic_findings: list[Finding]
    ai_findings: list[Finding]
    rule_set_hash: str


class ValidateContentInput(StrictModel):
    project_id: UUID
    page_id: UUID
    content_version_id: UUID
    include_seo: bool = True
    include_brand: bool = True


class ValidateContentOutput(StrictModel):
    report_id: UUID
    findings: list[Finding]
    component_scores: dict[str, float]
    blocking: bool


class FindInternalLinkOpportunitiesInput(StrictModel):
    project_id: UUID
    source_page_id: UUID
    content_version_id: UUID
    limit: int = Field(default=10, ge=1, le=50)


class LinkOpportunity(StrictModel):
    target_page_id: UUID
    relationship_type: str
    score: float = Field(ge=0, le=1)
    score_components: dict[str, float]
    evidence: list[str]


class FindInternalLinkOpportunitiesOutput(StrictModel):
    opportunities: list[LinkOpportunity]
    algorithm_version: str


class SuggestAnchorTextInput(StrictModel):
    project_id: UUID
    source_page_id: UUID
    target_page_id: UUID
    content_version_id: UUID
    max_suggestions: int = Field(default=3, ge=1, le=10)


class AnchorSuggestion(StrictModel):
    text: str
    rationale: str
    risk_flags: list[str]


class SuggestAnchorTextOutput(StrictModel):
    proposal_id: UUID
    suggestions: list[AnchorSuggestion]


class ValidateInternalLinksInput(StrictModel):
    project_id: UUID
    page_id: UUID
    content_version_id: UUID


class ValidateInternalLinksOutput(StrictModel):
    analysis_id: UUID
    findings: list[Finding]
    incoming_count: int = Field(ge=0)
    outgoing_count: int = Field(ge=0)


class GetBrandVoiceInput(StrictModel):
    project_id: UUID
    locale: str | None = None


class GetBrandVoiceOutput(StrictModel):
    profile: VersionRef
    attributes: dict[str, object]
    rules: list[RuleSummary]


class CheckBrandVoiceInput(StrictModel):
    project_id: UUID
    page_id: UUID
    content_version_id: UUID
    profile_version_id: UUID


class CheckBrandVoiceOutput(StrictModel):
    analysis_id: UUID
    findings: list[Finding]


class SearchKnowledgeBaseInput(StrictModel):
    project_id: UUID
    query: str
    source_types: list[str] = Field(default_factory=list)
    limit: int = Field(default=8, ge=1, le=30)


class KnowledgeHit(StrictModel):
    chunk_id: UUID
    document_id: UUID
    source_id: UUID
    excerpt: str
    score: float = Field(ge=0, le=1)
    citation_label: str


class SearchKnowledgeBaseOutput(StrictModel):
    hits: list[KnowledgeHit]
    retrieval_version: str


class GetCompanyContextInput(StrictModel):
    project_id: UUID
    context_kinds: list[str]
    max_tokens: int = Field(default=4_000, ge=256, le=20_000)


class GetCompanyContextOutput(StrictModel):
    items: list[dict[str, object]]
    source_ids: list[UUID]
    token_count: int = Field(ge=0)
    truncated: bool


class SaveDraftInput(StrictModel):
    project_id: UUID
    page_id: UUID
    base_version_id: UUID
    document_json: dict[str, object]
    idempotency_key: str


class SaveDraftOutput(StrictModel):
    proposal: ProposedChange


class CreateVersionInput(StrictModel):
    project_id: UUID
    page_id: UUID
    base_version_id: UUID
    proposal_id: UUID | None = None
    change_summary: str


class CreateVersionOutput(StrictModel):
    proposal: ProposedChange


class PublicationAction(StrEnum):
    SAVE_CMS_DRAFT = "save_cms_draft"
    PUBLISH = "publish"


class PublishPageInput(StrictModel):
    project_id: UUID
    page_id: UUID
    content_version_id: UUID
    destination_id: UUID
    action: PublicationAction
    approval_id: UUID
    idempotency_key: str


class PublishPageOutput(StrictModel):
    publication_run_id: UUID
    status: str
    external_url: str | None = None
