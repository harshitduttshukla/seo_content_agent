"""Pydantic schemas for Content Map graph projections, layout, validation, and versioning."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContentMapNodeData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str
    title: str = ""
    subtitle: str = ""
    status: str = ""
    entity_id: UUID
    node_type: str  # "pillar", "topic", "cluster", "page"
    primary_keyword: str = ""
    intent: str = ""
    priority: int = 1
    business_value: float = 0.0
    url: str = ""
    page_type: str = ""
    content_type: str = ""
    cluster_id: UUID | None = None
    topic_id: UUID | None = None
    pillar_id: UUID | None = None
    inbound_links_count: int = 0
    outbound_links_count: int = 0
    flags: list[str] = Field(default_factory=list)
    metrics: dict[str, object] = Field(default_factory=dict)


class ContentMapNodeDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    type: str  # "pillar", "topic", "cluster", "page"
    position: dict[str, float] | None = None
    data: ContentMapNodeData


class ContentMapEdgeDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    source: str
    target: str
    type: str  # "contains", "targets", "supports", "related", "child_of", "links_to", "references"
    label: str = ""
    data: dict[str, object] = Field(default_factory=dict)


class ContentMapStats(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_pillars: int = 0
    total_topics: int = 0
    total_clusters: int = 0
    total_pages: int = 0
    planned_pages: int = 0
    existing_pages: int = 0
    orphan_pages: int = 0
    cannibalization_warnings: int = 0


class ContentMapGraphResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    graph_revision: int = 1
    nodes: list[ContentMapNodeDTO]
    edges: list[ContentMapEdgeDTO]
    stats: ContentMapStats = Field(default_factory=ContentMapStats)


class NodePositionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    position_x: float
    position_y: float


class ContentMapLayoutUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positions: list[NodePositionUpdate]


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    severity: str  # "error", "warning", "info"
    issue_type: str
    entity_type: str
    entity_id: UUID | None = None
    entity_label: str
    reason: str
    recommended_action: str


class ContentMapValidationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    is_valid: bool
    total_issues: int
    issues: list[ValidationIssue]


class ContentArchitectureVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_summary: str = "Content architecture version snapshot"


class ContentArchitectureVersionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    version: int
    change_summary: str
    snapshot_data: dict[str, object]
    created_by_id: UUID | None = None
    created_at: datetime


class ContentArchitectureVersionList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[ContentArchitectureVersionDetail]
