"""Pydantic schemas for the Keywords domain."""

from datetime import datetime
from uuid import UUID

from app.domains.keywords.models import (
    ClusterStatus,
    FunnelStage,
    KeywordSource,
    KeywordStatus,
    SearchIntent,
)
from pydantic import BaseModel, ConfigDict, Field


class KeywordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword: str = Field(min_length=1, max_length=500)
    search_volume: int = Field(default=0, ge=0)
    keyword_difficulty: float = Field(default=0.0, ge=0.0, le=100.0)
    cpc: float = Field(default=0.0, ge=0.0)
    intent: SearchIntent | str = Field(default=SearchIntent.UNKNOWN)
    funnel_stage: FunnelStage | str = Field(default=FunnelStage.TOFU)
    source: KeywordSource | str = Field(default=KeywordSource.MANUAL)
    website_id: UUID | None = None


class KeywordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword: str | None = Field(default=None, min_length=1, max_length=500)
    search_volume: int | None = Field(default=None, ge=0)
    keyword_difficulty: float | None = Field(default=None, ge=0.0, le=100.0)
    cpc: float | None = Field(default=None, ge=0.0)
    intent: SearchIntent | str | None = None
    funnel_stage: FunnelStage | str | None = None
    business_value_score: float | None = Field(default=None, ge=0.0, le=100.0)
    priority_score: float | None = Field(default=None, ge=0.0, le=100.0)
    status: KeywordStatus | str | None = None


class KeywordDetail(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    website_id: UUID | None = None
    keyword: str
    normalized_keyword: str
    search_volume: int
    keyword_difficulty: float
    cpc: float
    intent: str
    intent_confidence: float
    funnel_stage: str
    business_value_score: float
    priority_score: float
    source: str
    status: str
    provider_metadata: dict[str, object] = Field(default_factory=dict)
    cluster_id: UUID | None = None
    cluster_name: str | None = None
    target_page_id: UUID | None = None
    target_page_url: str | None = None
    created_at: datetime
    updated_at: datetime


class KeywordList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[KeywordDetail]
    total_count: int = 0


class KeywordDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword_id: UUID
    keyword: str
    message: str


class KeywordImportRowSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    row_number: int
    keyword: str
    status: str
    error_message: str | None = None


class KeywordImportResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    filename: str
    source: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    created_rows: int
    updated_rows: int
    status: str
    error_summary: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ClusteringRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    similarity_threshold: float = Field(default=0.50, ge=0.1, le=1.0)
    include_archived: bool = Field(default=False)


class ClusteringRunResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    status: str
    algorithm_version: str
    parameters: dict[str, object]
    keyword_count: int
    cluster_count: int
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class KeywordClusterMemberDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    keyword_id: UUID
    keyword: str
    search_volume: int
    keyword_difficulty: float
    cpc: float
    intent: str
    priority_score: float
    business_value_score: float
    is_primary: bool
    similarity_score: float


class KeywordClusterDetail(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    topic_id: UUID | None = None
    topic_name: str | None = None
    clustering_run_id: UUID | None = None
    cluster_name: str
    primary_keyword_id: UUID | None = None
    primary_keyword: str | None = None
    intent: str
    cluster_score: float
    status: str
    rationale: str
    member_count: int = 0
    members: list[KeywordClusterMemberDetail] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class KeywordClusterList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[KeywordClusterDetail]


class KeywordClusterDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster_id: UUID
    cluster_name: str
    message: str


class ClusterUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster_name: str | None = None
    primary_keyword_id: UUID | None = None
    topic_id: UUID | None = None
    status: ClusterStatus | str | None = None
    rationale: str | None = None


class ClusterMergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_cluster_ids: list[UUID] = Field(min_length=2)
    target_cluster_name: str = Field(min_length=1)
    primary_keyword_id: UUID | None = None


class MoveKeywordsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword_ids: list[UUID] = Field(min_length=1)
    target_cluster_id: UUID
