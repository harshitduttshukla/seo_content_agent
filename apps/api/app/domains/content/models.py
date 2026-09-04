"""Content domain database models for pages, architecture, and opportunities."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from app.core.models import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class ContentStatus(StrEnum):
    INDEXED = "indexed"
    DUPLICATE = "duplicate"
    FAILED = "failed"
    REDIRECT = "redirect"
    BLOCKED = "blocked"


class ArchitectureStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    ARCHIVED = "archived"


class MappingType(StrEnum):
    PRIMARY_TARGET = "PRIMARY_TARGET"
    SECONDARY_TARGET = "SECONDARY_TARGET"
    SUPPORTING_PAGE = "SUPPORTING_PAGE"
    NO_TARGET = "NO_TARGET"
    NEW_PAGE_REQUIRED = "NEW_PAGE_REQUIRED"


class MappingSource(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    AI = "AI"
    MANUAL = "MANUAL"


class MappingStatus(StrEnum):
    PROPOSED = "proposed"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class OpportunityAction(StrEnum):
    NEW_PAGE = "NEW_PAGE"
    UPDATE_EXISTING_PAGE = "UPDATE_EXISTING_PAGE"
    MERGE_EXISTING_PAGES = "MERGE_EXISTING_PAGES"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class OpportunityStatus(StrEnum):
    PROPOSED = "proposed"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class ContentPage(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "content_pages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_pages_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_content_pages_website_id_websites",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "content_status IN ('indexed', 'duplicate', 'failed', 'redirect', 'blocked')",
            name="ck_content_pages_status_allowed",
        ),
        Index(
            "uq_content_pages_website_normalized_url",
            "website_id",
            "normalized_url",
            unique=True,
        ),
        Index("ix_content_pages_website_status", "website_id", "content_status"),
        Index("ix_content_pages_website_hash", "website_id", "content_hash"),
        Index(
            "ix_content_pages_org_proj_status", "organization_id", "project_id", "content_status"
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    website_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    meta_description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="en")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False, default="text/html")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    content_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ContentStatus.INDEXED
    )
    raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleaned_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    structured_content: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    headings: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    images: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContentPageVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "content_page_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["page_id"],
            ["content_pages.id"],
            name="fk_content_page_versions_page_id_content_pages",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["crawl_job_id"],
            ["crawl_jobs.id"],
            name="fk_content_page_versions_crawl_job_id_crawl_jobs",
            ondelete="SET NULL",
        ),
        Index("ix_content_page_versions_page_created", "page_id", "created_at"),
        Index("ix_content_page_versions_page_hash", "page_id", "content_hash"),
    )

    page_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    crawl_job_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    structured_content: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    cleaned_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class PageLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "page_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_page_links_website_id_websites",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_page_id"],
            ["content_pages.id"],
            name="fk_page_links_source_page_id_content_pages",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_page_id"],
            ["content_pages.id"],
            name="fk_page_links_target_page_id_content_pages",
            ondelete="SET NULL",
        ),
        Index("ix_page_links_website_source", "website_id", "source_page_id"),
        Index("ix_page_links_website_target_page", "website_id", "target_page_id"),
        Index("ix_page_links_website_normalized_target", "website_id", "normalized_target_url"),
    )

    website_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_page_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    target_page_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    anchor_text: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    rel: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    nofollow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ugc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sponsored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class ContentPillar(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "content_pillars"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_pillars_org_proj_projects",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('proposed', 'approved', 'archived')",
            name="ck_content_pillars_status_allowed",
        ),
        Index("uq_content_pillars_project_slug", "project_id", "slug", unique=True),
        Index("ix_content_pillars_proj_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    business_goal: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ArchitectureStatus.PROPOSED
    )


class Topic(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "topics"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_topics_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["pillar_id"],
            ["content_pillars.id"],
            name="fk_topics_pillar_id_content_pillars",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('proposed', 'approved', 'archived')",
            name="ck_topics_status_allowed",
        ),
        Index("uq_topics_project_slug", "project_id", "slug", unique=True),
        Index("ix_topics_proj_pillar", "project_id", "pillar_id"),
        Index("ix_topics_proj_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    pillar_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ArchitectureStatus.PROPOSED
    )


class KeywordPageMapping(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "keyword_page_mappings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_keyword_page_mappings_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_keyword_page_mappings_website_id_websites",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["keyword_id"],
            ["keywords.id"],
            name="fk_keyword_page_mappings_keyword_id_keywords",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["page_id"],
            ["content_pages.id"],
            name="fk_keyword_page_mappings_page_id_content_pages",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "mapping_type IN ('PRIMARY_TARGET', 'SECONDARY_TARGET', "
            "'SUPPORTING_PAGE', 'NO_TARGET', 'NEW_PAGE_REQUIRED')",
            name="ck_keyword_page_mappings_type_allowed",
        ),
        CheckConstraint(
            "source IN ('DETERMINISTIC', 'AI', 'MANUAL')",
            name="ck_keyword_page_mappings_source_allowed",
        ),
        CheckConstraint(
            "status IN ('proposed', 'reviewed', 'approved', 'rejected')",
            name="ck_keyword_page_mappings_status_allowed",
        ),
        Index("ix_keyword_page_mappings_kw_id", "keyword_id"),
        Index("ix_keyword_page_mappings_page_id", "page_id"),
        Index("ix_keyword_page_mappings_site_type", "website_id", "mapping_type"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    website_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    keyword_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    page_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    mapping_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=MappingType.PRIMARY_TARGET
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=MappingSource.DETERMINISTIC
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=MappingStatus.PROPOSED)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ContentOpportunity(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "content_opportunities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_opportunities_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_content_opportunities_website_id_websites",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["cluster_id"],
            ["keyword_clusters.id"],
            name="fk_content_opportunities_cluster_id_keyword_clusters",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["keyword_id"],
            ["keywords.id"],
            name="fk_content_opportunities_keyword_id_keywords",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["existing_page_id"],
            ["content_pages.id"],
            name="fk_content_opportunities_page_id_content_pages",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "action IN ('NEW_PAGE', 'UPDATE_EXISTING_PAGE', 'MERGE_EXISTING_PAGES', "
            "'REVIEW_REQUIRED')",
            name="ck_content_opportunities_action_allowed",
        ),
        CheckConstraint(
            "status IN ('proposed', 'reviewed', 'approved', 'rejected')",
            name="ck_content_opportunities_status_allowed",
        ),
        Index("ix_content_opportunities_site_action", "website_id", "action"),
        Index("ix_content_opportunities_proj_status", "project_id", "status"),
        Index("ix_content_opportunities_priority", "project_id", "priority"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    website_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    cluster_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    keyword_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(
        String(32), nullable=False, default=OpportunityAction.NEW_PAGE
    )
    priority: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    business_value_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    existing_page_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=OpportunityStatus.PROPOSED
    )
