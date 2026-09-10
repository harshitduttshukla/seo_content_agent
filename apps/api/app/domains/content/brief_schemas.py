"""Pydantic schemas for Content Briefs and Content Brief Versioning."""

from datetime import datetime
from uuid import UUID

from app.domains.content.editor_models import BriefStatus
from pydantic import BaseModel, ConfigDict, Field, field_validator


class InternalLinkTarget(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target_page_id: UUID | None = None
    title: str = ""
    url: str = ""
    anchor_text: str = ""
    reason: str = ""


class BrandRequirements(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tone: str = "Professional, Authoritative, Clear"
    voice: str = "Knowledgeable, helpful, direct"
    style: str = "Concise paragraphs, informative headers, actionable advice"
    words_to_avoid: list[str] = Field(default_factory=list)
    formatting_rules: list[str] = Field(default_factory=list)


class ContentBriefCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_keyword: str | None = None
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str = "INFORMATIONAL"
    target_audience: str = ""
    business_goal: str = ""
    content_type: str = "GUIDE"
    recommended_title: str = ""
    recommended_url: str = ""
    meta_title: str = ""
    meta_description: str = ""
    target_word_count: int = Field(default=1500, ge=100, le=50000)
    required_topics: list[str] = Field(default_factory=list)
    key_entities: list[str] = Field(default_factory=list)
    questions_to_answer: list[str] = Field(default_factory=list)
    internal_link_targets: list[InternalLinkTarget] = Field(default_factory=list)
    external_source_requirements: list[str] = Field(default_factory=list)
    content_requirements: list[str] = Field(default_factory=list)
    brand_requirements: BrandRequirements = Field(default_factory=BrandRequirements)


class ContentBriefUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_keyword: str | None = None
    secondary_keywords: list[str] | None = None
    search_intent: str | None = None
    target_audience: str | None = None
    business_goal: str | None = None
    content_type: str | None = None
    recommended_title: str | None = None
    recommended_url: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    target_word_count: int | None = Field(default=None, ge=100, le=50000)
    required_topics: list[str] | None = None
    key_entities: list[str] | None = None
    questions_to_answer: list[str] | None = None
    internal_link_targets: list[InternalLinkTarget] | None = None
    external_source_requirements: list[str] | None = None
    content_requirements: list[str] | None = None
    brand_requirements: BrandRequirements | None = None
    status: BriefStatus | None = None


class ContentBriefApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_summary: str = Field(default="Content brief approved for production", max_length=1000)


class ContentBriefDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    website_id: UUID | None
    page_id: UUID
    seo_guide_id: UUID | None
    version: int
    status: str
    primary_keyword: str = ""
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str = "INFORMATIONAL"
    target_audience: str = ""
    business_goal: str = ""
    content_type: str = "GUIDE"
    recommended_title: str = ""
    recommended_url: str = ""
    meta_title: str = ""
    meta_description: str = ""
    target_word_count: int = 1500
    required_topics: list[str] = Field(default_factory=list)
    key_entities: list[str] = Field(default_factory=list)
    questions_to_answer: list[str] = Field(default_factory=list)
    internal_link_targets: list[dict[str, object]] = Field(default_factory=list)
    external_source_requirements: list[str] = Field(default_factory=list)
    content_requirements: list[str] = Field(default_factory=list)
    brand_requirements: dict[str, object] = Field(default_factory=dict)
    created_by_id: UUID | None = None
    updated_by_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "primary_keyword",
        "search_intent",
        "target_audience",
        "business_goal",
        "content_type",
        "recommended_title",
        "recommended_url",
        "meta_title",
        "meta_description",
        mode="before",
    )
    @classmethod
    def coerce_none_str(cls, v: object) -> object:
        return "" if v is None else v

    @field_validator(
        "secondary_keywords",
        "required_topics",
        "key_entities",
        "questions_to_answer",
        "internal_link_targets",
        "external_source_requirements",
        "content_requirements",
        mode="before",
    )
    @classmethod
    def coerce_none_list(cls, v: object) -> object:
        return [] if v is None else v

    @field_validator("brand_requirements", mode="before")
    @classmethod
    def coerce_none_dict(cls, v: object) -> object:
        return {} if v is None else v


class ContentBriefVersionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    brief_id: UUID
    organization_id: UUID
    project_id: UUID
    version: int
    snapshot_data: dict[str, object]
    change_summary: str
    created_by_id: UUID | None
    created_at: datetime


class ContentBriefVersionList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[ContentBriefVersionDetail]
