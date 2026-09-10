"""Keywords domain database models for keyword inventory, imports, and clustering."""

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


class KeywordSource(StrEnum):
    MANUAL = "MANUAL"
    CSV = "CSV"
    SEARCH_CONSOLE = "SEARCH_CONSOLE"
    KEYWORD_PROVIDER = "KEYWORD_PROVIDER"
    AI_DISCOVERY = "AI_DISCOVERY"
    IMPORT = "IMPORT"


class SearchIntent(StrEnum):
    INFORMATIONAL = "INFORMATIONAL"
    COMMERCIAL = "COMMERCIAL"
    TRANSACTIONAL = "TRANSACTIONAL"
    NAVIGATIONAL = "NAVIGATIONAL"
    LOCAL = "LOCAL"
    UNKNOWN = "UNKNOWN"


class FunnelStage(StrEnum):
    TOFU = "TOFU"
    MOFU = "MOFU"
    BOFU = "BOFU"


class KeywordStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    IGNORED = "ignored"


class ClusterStatus(StrEnum):
    PROPOSED = "proposed"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class ClusteringRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Keyword(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "keywords"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_keywords_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_keywords_website_id_websites",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('active', 'archived', 'ignored')",
            name="ck_keywords_status_allowed",
        ),
        CheckConstraint(
            "intent IN ('INFORMATIONAL', 'COMMERCIAL', 'TRANSACTIONAL', "
            "'NAVIGATIONAL', 'LOCAL', 'UNKNOWN')",
            name="ck_keywords_intent_allowed",
        ),
        CheckConstraint(
            "funnel_stage IN ('TOFU', 'MOFU', 'BOFU')",
            name="ck_keywords_funnel_stage_allowed",
        ),
        Index(
            "uq_keywords_project_normalized_keyword",
            "project_id",
            "normalized_keyword",
            unique=True,
        ),
        Index("ix_keywords_org_proj_status", "organization_id", "project_id", "status"),
        Index("ix_keywords_proj_intent", "project_id", "intent"),
        Index("ix_keywords_proj_priority", "project_id", "priority_score"),
        Index("ix_keywords_proj_volume", "project_id", "search_volume"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    website_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    search_volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    keyword_difficulty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cpc: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    intent: Mapped[str] = mapped_column(String(32), nullable=False, default=SearchIntent.UNKNOWN)
    intent_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    funnel_stage: Mapped[str] = mapped_column(String(16), nullable=False, default=FunnelStage.TOFU)
    business_value_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default=KeywordSource.MANUAL)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=KeywordStatus.ACTIVE)
    provider_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )


class KeywordImport(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "keyword_imports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_keyword_imports_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_keyword_imports_created_by_id_users",
            ondelete="SET NULL",
        ),
        Index("ix_keyword_imports_proj_created", "project_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default=KeywordSource.CSV)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KeywordImportRow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "keyword_import_rows"
    __table_args__ = (
        ForeignKeyConstraint(
            ["import_id"],
            ["keyword_imports.id"],
            name="fk_keyword_import_rows_import_id_keyword_imports",
            ondelete="CASCADE",
        ),
        Index("ix_keyword_import_rows_import_row", "import_id", "row_number"),
    )

    import_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, server_default="{}")
    keyword: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_keyword_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class ClusteringRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clustering_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_clustering_runs_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_clustering_runs_created_by_id_users",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_clustering_runs_status_allowed",
        ),
        Index("ix_clustering_runs_proj_created", "project_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ClusteringRunStatus.COMPLETED
    )
    algorithm_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="keyword_cluster_v1"
    )
    parameters: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    keyword_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cluster_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KeywordCluster(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "keyword_clusters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_keyword_clusters_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["clustering_run_id"],
            ["clustering_runs.id"],
            name="fk_keyword_clusters_run_id_clustering_runs",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["primary_keyword_id"],
            ["keywords.id"],
            name="fk_keyword_clusters_primary_kw_keywords",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('proposed', 'reviewed', 'approved', 'rejected')",
            name="ck_keyword_clusters_status_allowed",
        ),
        Index("ix_keyword_clusters_proj_status", "project_id", "status"),
        Index("ix_keyword_clusters_proj_intent", "project_id", "intent"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    topic_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    clustering_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    cluster_name: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_keyword_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    intent: Mapped[str] = mapped_column(String(32), nullable=False, default=SearchIntent.UNKNOWN)
    cluster_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ClusterStatus.PROPOSED)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")


class KeywordClusterMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "keyword_cluster_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["cluster_id"],
            ["keyword_clusters.id"],
            name="fk_keyword_cluster_members_cluster_id_keyword_clusters",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["keyword_id"],
            ["keywords.id"],
            name="fk_keyword_cluster_members_keyword_id_keywords",
            ondelete="CASCADE",
        ),
        Index(
            "uq_keyword_cluster_members_cluster_kw",
            "cluster_id",
            "keyword_id",
            unique=True,
        ),
        Index("ix_keyword_cluster_members_kw_id", "keyword_id"),
    )

    cluster_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    keyword_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
