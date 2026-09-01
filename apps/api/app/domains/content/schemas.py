"""Pydantic schemas for content pages, versions, and links."""

from datetime import datetime
from uuid import UUID

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
