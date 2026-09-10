"""Pydantic schemas for internal linking relationships, link opportunities, and orphan analysis."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PageRelationshipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_page_id: UUID
    target_page_id: UUID
    relationship_type: str = "SUPPORTS"
    anchor_text: str = ""
    priority: int = Field(default=1, ge=1, le=100)
    reason: str = ""


class PageRelationshipDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    source_page_id: UUID
    source_page_title: str = ""
    source_page_url: str = ""
    target_page_id: UUID
    target_page_title: str = ""
    target_page_url: str = ""
    relationship_type: str
    anchor_text: str
    priority: int
    reason: str
    confidence: float
    status: str
    created_at: datetime


class PageRelationshipList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[PageRelationshipDetail]


class LinkOpportunityDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    source_page_id: UUID
    source_page_title: str = ""
    source_page_url: str = ""
    target_page_id: UUID
    target_page_title: str = ""
    target_page_url: str = ""
    anchor_suggestion: str
    reason: str
    confidence: float
    priority: int
    status: str
    created_at: datetime


class LinkOpportunityList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[LinkOpportunityDetail]
    total: int = 0


class LinkOpportunityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "APPROVED"  # "APPROVED" or "REJECTED"


class InternalLinksSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page_id: UUID
    crawled_inbound_links: list[dict[str, object]] = Field(default_factory=list)
    crawled_outbound_links: list[dict[str, object]] = Field(default_factory=list)
    planned_inbound_relationships: list[PageRelationshipDetail] = Field(default_factory=list)
    planned_outbound_relationships: list[PageRelationshipDetail] = Field(default_factory=list)
    recommended_opportunities: list[LinkOpportunityDetail] = Field(default_factory=list)


class OrphanPageDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page_id: UUID
    title: str
    url: str
    page_type: str
    inbound_links: int
    priority: int
    primary_keyword: str


class OrphanPageList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[OrphanPageDetail]
    total: int = 0
