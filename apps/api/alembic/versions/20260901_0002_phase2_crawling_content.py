"""Phase 2 crawling, website intelligence, and content indexing foundation.

Revision ID: 20260901_0002
Revises: 20260901_0001
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260901_0002"
down_revision: str | None = "20260901_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_column(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    # 1. crawl_jobs table
    op.create_table(
        "crawl_jobs",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("website_id"),
        sa.Column("status", sa.String(32), server_default="queued", nullable=False),
        sa.Column(
            "configuration", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("pages_discovered", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pages_crawled", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pages_failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pages_skipped", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        uuid_column("requested_by_id", nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'paused', 'completed', 'failed', 'cancelled')",
            name="ck_crawl_jobs_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_crawl_jobs_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_crawl_jobs_website_id_websites",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"],
            ["users.id"],
            name="fk_crawl_jobs_requested_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_crawl_jobs"),
    )
    op.create_index(
        "ix_crawl_jobs_website_status", "crawl_jobs", ["website_id", "status"]
    )
    op.create_index(
        "ix_crawl_jobs_org_proj_created",
        "crawl_jobs",
        ["organization_id", "project_id", "created_at"],
    )

    # 2. crawl_urls table
    op.create_table(
        "crawl_urls",
        uuid_column("id"),
        uuid_column("crawl_job_id"),
        uuid_column("website_id"),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("normalized_url", sa.String(2048), nullable=False),
        sa.Column("status", sa.String(32), server_default="discovered", nullable=False),
        sa.Column("depth", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source", sa.String(64), server_default="seed", nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("redirect_url", sa.String(2048), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("crawled_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('discovered', 'queued', 'crawling', 'crawled', 'failed', 'skipped', 'blocked')",
            name="ck_crawl_urls_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["crawl_job_id"],
            ["crawl_jobs.id"],
            name="fk_crawl_urls_crawl_job_id_crawl_jobs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_crawl_urls_website_id_websites",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_crawl_urls"),
    )
    op.create_index("ix_crawl_urls_job_status", "crawl_urls", ["crawl_job_id", "status"])
    op.create_index(
        "ix_crawl_urls_job_normalized_url", "crawl_urls", ["crawl_job_id", "normalized_url"]
    )

    # 3. crawl_events table
    op.create_table(
        "crawl_events",
        uuid_column("id"),
        uuid_column("crawl_job_id"),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["crawl_job_id"],
            ["crawl_jobs.id"],
            name="fk_crawl_events_crawl_job_id_crawl_jobs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_crawl_events"),
    )
    op.create_index(
        "ix_crawl_events_job_occurred", "crawl_events", ["crawl_job_id", "occurred_at"]
    )

    # 4. content_pages table
    op.create_table(
        "content_pages",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("website_id"),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("normalized_url", sa.String(2048), nullable=False),
        sa.Column("canonical_url", sa.String(2048), nullable=True),
        sa.Column("title", sa.String(500), server_default="", nullable=False),
        sa.Column("meta_description", sa.String(1000), server_default="", nullable=False),
        sa.Column("language", sa.String(20), server_default="en", nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(120), server_default="text/html", nullable=False),
        sa.Column("word_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("content_hash", sa.String(64), server_default="", nullable=False),
        sa.Column("content_status", sa.String(32), server_default="indexed", nullable=False),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("cleaned_content", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "structured_content",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "headings", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "images", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "content_status IN ('indexed', 'duplicate', 'failed', 'redirect', 'blocked')",
            name="ck_content_pages_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_pages_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_content_pages_website_id_websites",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_pages"),
    )
    op.create_index(
        "uq_content_pages_website_normalized_url",
        "content_pages",
        ["website_id", "normalized_url"],
        unique=True,
    )
    op.create_index(
        "ix_content_pages_website_status", "content_pages", ["website_id", "content_status"]
    )
    op.create_index(
        "ix_content_pages_website_hash", "content_pages", ["website_id", "content_hash"]
    )
    op.create_index(
        "ix_content_pages_org_proj_status",
        "content_pages",
        ["organization_id", "project_id", "content_status"],
    )

    # 5. content_page_versions table
    op.create_table(
        "content_page_versions",
        uuid_column("id"),
        uuid_column("page_id"),
        uuid_column("crawl_job_id", nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column(
            "structured_content",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("cleaned_content", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["content_pages.id"],
            name="fk_content_page_versions_page_id_content_pages",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["crawl_job_id"],
            ["crawl_jobs.id"],
            name="fk_content_page_versions_crawl_job_id_crawl_jobs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_page_versions"),
    )
    op.create_index(
        "ix_content_page_versions_page_created",
        "content_page_versions",
        ["page_id", "created_at"],
    )
    op.create_index(
        "ix_content_page_versions_page_hash",
        "content_page_versions",
        ["page_id", "content_hash"],
    )

    # 6. page_links table
    op.create_table(
        "page_links",
        uuid_column("id"),
        uuid_column("website_id"),
        uuid_column("source_page_id"),
        uuid_column("target_page_id", nullable=True),
        sa.Column("target_url", sa.String(2048), nullable=False),
        sa.Column("normalized_target_url", sa.String(2048), nullable=False),
        sa.Column("anchor_text", sa.String(500), server_default="", nullable=False),
        sa.Column("rel", sa.String(120), nullable=True),
        sa.Column("is_internal", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("nofollow", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("ugc", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("sponsored", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_page_links_website_id_websites",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_page_id"],
            ["content_pages.id"],
            name="fk_page_links_source_page_id_content_pages",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_page_id"],
            ["content_pages.id"],
            name="fk_page_links_target_page_id_content_pages",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_page_links"),
    )
    op.create_index(
        "ix_page_links_website_source", "page_links", ["website_id", "source_page_id"]
    )
    op.create_index(
        "ix_page_links_website_target_page", "page_links", ["website_id", "target_page_id"]
    )
    op.create_index(
        "ix_page_links_website_normalized_target",
        "page_links",
        ["website_id", "normalized_target_url"],
    )


def downgrade() -> None:
    op.drop_table("page_links")
    op.drop_table("content_page_versions")
    op.drop_table("content_pages")
    op.drop_table("crawl_events")
    op.drop_table("crawl_urls")
    op.drop_table("crawl_jobs")
