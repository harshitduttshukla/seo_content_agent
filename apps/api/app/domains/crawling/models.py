"""Crawling domain database models."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import (
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


class CrawlJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CrawlUrlStatus(StrEnum):
    DISCOVERED = "discovered"
    QUEUED = "queued"
    CRAWLING = "crawling"
    CRAWLED = "crawled"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class CrawlJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crawl_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_crawl_jobs_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_crawl_jobs_website_id_websites",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["requested_by_id"],
            ["users.id"],
            name="fk_crawl_jobs_requested_by_id_users",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'paused', 'completed', 'failed', 'cancelled')",
            name="ck_crawl_jobs_status_allowed",
        ),
        Index("ix_crawl_jobs_website_status", "website_id", "status"),
        Index("ix_crawl_jobs_org_proj_created", "organization_id", "project_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    website_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=CrawlJobStatus.QUEUED)
    configuration: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    pages_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_crawled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class CrawlUrl(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "crawl_urls"
    __table_args__ = (
        ForeignKeyConstraint(
            ["crawl_job_id"],
            ["crawl_jobs.id"],
            name="fk_crawl_urls_crawl_job_id_crawl_jobs",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_crawl_urls_website_id_websites",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('discovered', 'queued', 'crawling', 'crawled', 'failed', "
            "'skipped', 'blocked')",
            name="ck_crawl_urls_status_allowed",
        ),
        Index("ix_crawl_urls_job_status", "crawl_job_id", "status"),
        Index("ix_crawl_urls_job_normalized_url", "crawl_job_id", "normalized_url"),
    )

    crawl_job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    website_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CrawlUrlStatus.DISCOVERED
    )
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="seed")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redirect_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CrawlEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "crawl_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["crawl_job_id"],
            ["crawl_jobs.id"],
            name="fk_crawl_events_crawl_job_id_crawl_jobs",
            ondelete="CASCADE",
        ),
        Index("ix_crawl_events_job_occurred", "crawl_job_id", "occurred_at"),
    )

    crawl_job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
