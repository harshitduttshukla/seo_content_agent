"""Content domain database models for pages, versions, and internal link graph."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from app.core.models import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
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
