"""Pydantic schemas for crawling and website verification."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CrawlConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_pages: int = Field(default=200, ge=1, le=2000, description="Maximum pages to crawl")
    max_depth: int = Field(default=4, ge=1, le=10, description="Maximum crawl depth")
    respect_robots: bool = Field(default=True, description="Respect robots.txt directives")
    crawl_delay: float = Field(
        default=0.2, ge=0.0, le=10.0, description="Politeness delay between fetches in seconds"
    )
    allowed_paths: list[str] = Field(default_factory=list, description="Subpath prefixes to allow")
    blocked_paths: list[str] = Field(default_factory=list, description="Subpath prefixes to block")
    include_subdomains: bool = Field(
        default=False, description="Include subdomains of verified host"
    )
    user_agent: str = Field(
        default="Antigravity-ContentAgent/1.0",
        max_length=200,
        description="Custom crawler User-Agent",
    )


class CrawlJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configuration: CrawlConfiguration = Field(default_factory=CrawlConfiguration)


class CrawlJobDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    website_id: UUID
    status: str
    configuration: dict[str, object]
    pages_discovered: int
    pages_crawled: int
    pages_failed: int
    pages_skipped: int
    error_count: int
    started_at: datetime | None
    completed_at: datetime | None
    requested_by_id: UUID | None
    error_summary: str | None
    created_at: datetime
    updated_at: datetime


class CrawlJobList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[CrawlJobDetail]


class CrawlStatusSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    website_id: UUID
    verification_status: str
    active_job: CrawlJobDetail | None = None
    last_job: CrawlJobDetail | None = None
    total_indexed_pages: int = 0


class WebsiteVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = Field(
        default="http_meta",
        description="Verification method: 'http_meta', 'http_header', or 'verification_file'",
    )


class WebsiteVerificationDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    website_id: UUID
    verification_status: str
    verified_at: datetime | None
    verification_token: str
    meta_tag_snippet: str
    file_snippet: str
