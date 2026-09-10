"""Pydantic schemas for SEO Guides, structured outlines, rules, and versions."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SEOGuideOutlineSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    level: int = Field(ge=1, le=6)
    title: str = Field(min_length=1, max_length=500)
    required: bool = True


class SEOGuideCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_keyword: str = ""
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str = "INFORMATIONAL"
    target_audience: str = ""
    recommended_title: str = ""
    meta_title: str = ""
    meta_description: str = ""
    recommended_url: str = ""
    content_type: str = "GUIDE"
    word_count_target: int = Field(default=1500, ge=100, le=50000)
    required_topics: list[str] = Field(default_factory=list)
    key_entities: list[str] = Field(default_factory=list)
    serp_notes: str = ""
    content_requirements: list[str] = Field(default_factory=list)
    outline: list[SEOGuideOutlineSection] = Field(default_factory=list)
    seo_rules: dict[str, object] = Field(default_factory=dict)


class SEOGuideUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_keyword: str | None = None
    secondary_keywords: list[str] | None = None
    search_intent: str | None = None
    target_audience: str | None = None
    recommended_title: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    recommended_url: str | None = None
    content_type: str | None = None
    word_count_target: int | None = Field(default=None, ge=100, le=50000)
    required_topics: list[str] | None = None
    key_entities: list[str] | None = None
    serp_notes: str | None = None
    content_requirements: list[str] | None = None
    outline: list[SEOGuideOutlineSection] | None = None
    seo_rules: dict[str, object] | None = None
    status: str | None = None


class SEOGuideDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    page_id: UUID
    version: int
    status: str
    primary_keyword: str
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str
    target_audience: str
    recommended_title: str
    meta_title: str
    meta_description: str
    recommended_url: str
    content_type: str
    word_count_target: int
    required_topics: list[str] = Field(default_factory=list)
    key_entities: list[str] = Field(default_factory=list)
    serp_notes: str
    content_requirements: list[str] = Field(default_factory=list)
    outline: list[SEOGuideOutlineSection] = Field(default_factory=list)
    seo_rules: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class SEOGuideVersionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    guide_id: UUID
    page_id: UUID
    version: int
    snapshot_data: dict[str, object]
    change_summary: str
    created_by_id: UUID | None = None
    created_at: datetime


class SEOGuideVersionList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[SEOGuideVersionDetail]
