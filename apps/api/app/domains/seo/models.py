"""SEO domain database models for SEO Guides, outlines, guidelines, and immutable versions."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from app.core.models import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin
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


class SEOGuideStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    ACTIVE = "active"
    ARCHIVED = "archived"


class SEOGuide(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "seo_guides"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_seo_guides_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["page_id"],
            ["planned_content_pages.id"],
            name="fk_seo_guides_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'active', 'archived')",
            name="ck_seo_guides_status_allowed",
        ),
        Index("uq_seo_guides_page_id", "page_id", unique=True),
        Index("ix_seo_guides_proj_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    page_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=SEOGuideStatus.DRAFT)
    primary_keyword: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    secondary_keywords: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    search_intent: Mapped[str] = mapped_column(String(32), nullable=False, default="INFORMATIONAL")
    target_audience: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    recommended_title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    meta_title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    meta_description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    recommended_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="GUIDE")
    word_count_target: Mapped[int] = mapped_column(Integer, nullable=False, default=1500)
    required_topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    key_entities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    serp_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_requirements: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    outline: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    seo_rules: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, server_default="{}")


class SEOGuideVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "seo_guide_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["guide_id"],
            ["seo_guides.id"],
            name="fk_seo_guide_versions_guide_id_seo_guides",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_seo_guide_versions_created_by_id_users",
            ondelete="SET NULL",
        ),
        Index("uq_seo_guide_versions_guide_version", "guide_id", "version", unique=True),
        Index("ix_seo_guide_versions_page_id", "page_id"),
    )

    guide_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    page_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_data: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    change_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
