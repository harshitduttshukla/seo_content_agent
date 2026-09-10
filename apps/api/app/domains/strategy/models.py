"""Strategy domain database models for SEO strategy and strategy versioning."""

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


class StrategyStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class SEOStrategy(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "seo_strategies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_seo_strategies_org_proj_projects",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_seo_strategies_status_allowed",
        ),
        Index("uq_seo_strategies_project_id", "project_id", unique=True),
        Index(
            "ix_seo_strategies_org_proj_status",
            "organization_id",
            "project_id",
            "status",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=StrategyStatus.ACTIVE)


class SEOStrategyVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "seo_strategy_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["strategy_id"],
            ["seo_strategies.id"],
            name="fk_seo_strategy_versions_strategy_id_seo_strategies",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_seo_strategy_versions_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_seo_strategy_versions_created_by_id_users",
            ondelete="SET NULL",
        ),
        Index(
            "uq_seo_strategy_versions_strategy_version",
            "strategy_id",
            "version",
            unique=True,
        ),
        Index(
            "ix_seo_strategy_versions_proj_version",
            "project_id",
            "version",
        ),
    )

    strategy_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    strategy_data: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
