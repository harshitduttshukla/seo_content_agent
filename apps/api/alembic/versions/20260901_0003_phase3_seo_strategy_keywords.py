"""Phase 3 SEO Strategy, Keyword Intelligence, and Content Architecture.

Revision ID: 20260901_0003
Revises: 20260901_0002
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260901_0003"
down_revision: str | None = "20260901_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_column(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def upgrade() -> None:
    # 1. seo_strategies
    op.create_table(
        "seo_strategies",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_seo_strategies_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_seo_strategies_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_seo_strategies"),
    )
    op.create_index(
        "uq_seo_strategies_project_id",
        "seo_strategies",
        ["project_id"],
        unique=True,
    )
    op.create_index(
        "ix_seo_strategies_org_proj_status",
        "seo_strategies",
        ["organization_id", "project_id", "status"],
    )

    # 2. seo_strategy_versions
    op.create_table(
        "seo_strategy_versions",
        uuid_column("id"),
        uuid_column("strategy_id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        sa.Column("version", sa.Integer(), nullable=False),
        uuid_column("created_by_id", nullable=True),
        sa.Column("change_summary", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "strategy_data",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["strategy_id"],
            ["seo_strategies.id"],
            name="fk_seo_strategy_versions_strategy_id_seo_strategies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_seo_strategy_versions_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_seo_strategy_versions_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_seo_strategy_versions"),
    )
    op.create_index(
        "uq_seo_strategy_versions_strategy_version",
        "seo_strategy_versions",
        ["strategy_id", "version"],
        unique=True,
    )
    op.create_index(
        "ix_seo_strategy_versions_proj_version",
        "seo_strategy_versions",
        ["project_id", "version"],
    )

    # 3. content_pillars
    op.create_table(
        "content_pillars",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("business_goal", sa.String(200), server_default="", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(32), server_default="proposed", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'archived')",
            name="ck_content_pillars_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_pillars_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_pillars"),
    )
    op.create_index(
        "uq_content_pillars_project_slug",
        "content_pillars",
        ["project_id", "slug"],
        unique=True,
    )
    op.create_index(
        "ix_content_pillars_proj_status",
        "content_pillars",
        ["project_id", "status"],
    )

    # 4. topics
    op.create_table(
        "topics",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("pillar_id", nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(32), server_default="proposed", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'archived')",
            name="ck_topics_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_topics_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pillar_id"],
            ["content_pillars.id"],
            name="fk_topics_pillar_id_content_pillars",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_topics"),
    )
    op.create_index(
        "uq_topics_project_slug",
        "topics",
        ["project_id", "slug"],
        unique=True,
    )
    op.create_index(
        "ix_topics_proj_pillar",
        "topics",
        ["project_id", "pillar_id"],
    )
    op.create_index(
        "ix_topics_proj_status",
        "topics",
        ["project_id", "status"],
    )

    # 5. keywords
    op.create_table(
        "keywords",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("website_id", nullable=True),
        sa.Column("keyword", sa.String(500), nullable=False),
        sa.Column("normalized_keyword", sa.String(500), nullable=False),
        sa.Column("search_volume", sa.Integer(), server_default="0", nullable=False),
        sa.Column("keyword_difficulty", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("cpc", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("intent", sa.String(32), server_default="UNKNOWN", nullable=False),
        sa.Column("intent_confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("funnel_stage", sa.String(16), server_default="TOFU", nullable=False),
        sa.Column("business_value_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("priority_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("source", sa.String(32), server_default="MANUAL", nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column(
            "provider_metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('active', 'archived', 'ignored')",
            name="ck_keywords_status_allowed",
        ),
        sa.CheckConstraint(
            "intent IN ('INFORMATIONAL', 'COMMERCIAL', 'TRANSACTIONAL', "
            "'NAVIGATIONAL', 'LOCAL', 'UNKNOWN')",
            name="ck_keywords_intent_allowed",
        ),
        sa.CheckConstraint(
            "funnel_stage IN ('TOFU', 'MOFU', 'BOFU')",
            name="ck_keywords_funnel_stage_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_keywords_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_keywords_website_id_websites",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_keywords"),
    )
    op.create_index(
        "uq_keywords_project_normalized_keyword",
        "keywords",
        ["project_id", "normalized_keyword"],
        unique=True,
    )
    op.create_index(
        "ix_keywords_org_proj_status",
        "keywords",
        ["organization_id", "project_id", "status"],
    )
    op.create_index("ix_keywords_proj_intent", "keywords", ["project_id", "intent"])
    op.create_index(
        "ix_keywords_proj_priority", "keywords", ["project_id", "priority_score"]
    )
    op.create_index(
        "ix_keywords_proj_volume", "keywords", ["project_id", "search_volume"]
    )

    # 6. keyword_imports
    op.create_table(
        "keyword_imports",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("source", sa.String(32), server_default="CSV", nullable=False),
        sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("valid_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("invalid_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicate_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(32), server_default="completed", nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        uuid_column("created_by_id", nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_keyword_imports_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_keyword_imports_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_keyword_imports"),
    )
    op.create_index(
        "ix_keyword_imports_proj_created",
        "keyword_imports",
        ["project_id", "created_at"],
    )

    # 7. keyword_import_rows
    op.create_table(
        "keyword_import_rows",
        uuid_column("id"),
        uuid_column("import_id"),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column(
            "raw_data",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(500), server_default="", nullable=False),
        sa.Column("status", sa.String(32), server_default="success", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        uuid_column("created_keyword_id", nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["import_id"],
            ["keyword_imports.id"],
            name="fk_keyword_import_rows_import_id_keyword_imports",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_keyword_import_rows"),
    )
    op.create_index(
        "ix_keyword_import_rows_import_row",
        "keyword_import_rows",
        ["import_id", "row_number"],
    )

    # 8. clustering_runs
    op.create_table(
        "clustering_runs",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        sa.Column("status", sa.String(32), server_default="completed", nullable=False),
        sa.Column(
            "algorithm_version",
            sa.String(64),
            server_default="keyword_cluster_v1",
            nullable=False,
        ),
        sa.Column(
            "parameters",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("keyword_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cluster_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        uuid_column("created_by_id", nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_clustering_runs_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_clustering_runs_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_clustering_runs_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_clustering_runs"),
    )
    op.create_index(
        "ix_clustering_runs_proj_created",
        "clustering_runs",
        ["project_id", "created_at"],
    )

    # 9. keyword_clusters
    op.create_table(
        "keyword_clusters",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("topic_id", nullable=True),
        uuid_column("clustering_run_id", nullable=True),
        sa.Column("cluster_name", sa.String(255), nullable=False),
        uuid_column("primary_keyword_id", nullable=True),
        sa.Column("intent", sa.String(32), server_default="UNKNOWN", nullable=False),
        sa.Column("cluster_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("status", sa.String(32), server_default="proposed", nullable=False),
        sa.Column("rationale", sa.Text(), server_default="", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('proposed', 'reviewed', 'approved', 'rejected')",
            name="ck_keyword_clusters_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_keyword_clusters_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name="fk_keyword_clusters_topic_id_topics",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["clustering_run_id"],
            ["clustering_runs.id"],
            name="fk_keyword_clusters_run_id_clustering_runs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["primary_keyword_id"],
            ["keywords.id"],
            name="fk_keyword_clusters_primary_kw_keywords",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_keyword_clusters"),
    )
    op.create_index(
        "ix_keyword_clusters_proj_status",
        "keyword_clusters",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_keyword_clusters_proj_intent",
        "keyword_clusters",
        ["project_id", "intent"],
    )

    # 10. keyword_cluster_members
    op.create_table(
        "keyword_cluster_members",
        uuid_column("id"),
        uuid_column("cluster_id"),
        uuid_column("keyword_id"),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("similarity_score", sa.Float(), server_default="1.0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["keyword_clusters.id"],
            name="fk_keyword_cluster_members_cluster_id_keyword_clusters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["keyword_id"],
            ["keywords.id"],
            name="fk_keyword_cluster_members_keyword_id_keywords",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_keyword_cluster_members"),
    )
    op.create_index(
        "uq_keyword_cluster_members_cluster_kw",
        "keyword_cluster_members",
        ["cluster_id", "keyword_id"],
        unique=True,
    )
    op.create_index(
        "ix_keyword_cluster_members_kw_id",
        "keyword_cluster_members",
        ["keyword_id"],
    )

    # 11. keyword_page_mappings
    op.create_table(
        "keyword_page_mappings",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("website_id"),
        uuid_column("keyword_id"),
        uuid_column("page_id", nullable=True),
        sa.Column(
            "mapping_type", sa.String(32), server_default="PRIMARY_TARGET", nullable=False
        ),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("source", sa.String(32), server_default="DETERMINISTIC", nullable=False),
        sa.Column("status", sa.String(32), server_default="proposed", nullable=False),
        sa.Column("rationale", sa.Text(), server_default="", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "mapping_type IN ('PRIMARY_TARGET', 'SECONDARY_TARGET', 'SUPPORTING_PAGE', "
            "'NO_TARGET', 'NEW_PAGE_REQUIRED')",
            name="ck_keyword_page_mappings_type_allowed",
        ),
        sa.CheckConstraint(
            "source IN ('DETERMINISTIC', 'AI', 'MANUAL')",
            name="ck_keyword_page_mappings_source_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'reviewed', 'approved', 'rejected')",
            name="ck_keyword_page_mappings_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_keyword_page_mappings_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_keyword_page_mappings_website_id_websites",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["keyword_id"],
            ["keywords.id"],
            name="fk_keyword_page_mappings_keyword_id_keywords",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["content_pages.id"],
            name="fk_keyword_page_mappings_page_id_content_pages",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_keyword_page_mappings"),
    )
    op.create_index(
        "ix_keyword_page_mappings_kw_id",
        "keyword_page_mappings",
        ["keyword_id"],
    )
    op.create_index(
        "ix_keyword_page_mappings_page_id",
        "keyword_page_mappings",
        ["page_id"],
    )
    op.create_index(
        "ix_keyword_page_mappings_site_type",
        "keyword_page_mappings",
        ["website_id", "mapping_type"],
    )

    # 12. content_opportunities
    op.create_table(
        "content_opportunities",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("website_id"),
        uuid_column("cluster_id", nullable=True),
        uuid_column("keyword_id", nullable=True),
        sa.Column("action", sa.String(32), server_default="NEW_PAGE", nullable=False),
        sa.Column("priority", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("business_value_score", sa.Float(), server_default="0.0", nullable=False),
        uuid_column("existing_page_id", nullable=True),
        sa.Column("reason", sa.Text(), server_default="", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("status", sa.String(32), server_default="proposed", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "action IN ('NEW_PAGE', 'UPDATE_EXISTING_PAGE', 'MERGE_EXISTING_PAGES', "
            "'REVIEW_REQUIRED')",
            name="ck_content_opportunities_action_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'reviewed', 'approved', 'rejected')",
            name="ck_content_opportunities_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_opportunities_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_content_opportunities_website_id_websites",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["keyword_clusters.id"],
            name="fk_content_opportunities_cluster_id_keyword_clusters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["keyword_id"],
            ["keywords.id"],
            name="fk_content_opportunities_keyword_id_keywords",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["existing_page_id"],
            ["content_pages.id"],
            name="fk_content_opportunities_page_id_content_pages",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_opportunities"),
    )
    op.create_index(
        "ix_content_opportunities_site_action",
        "content_opportunities",
        ["website_id", "action"],
    )
    op.create_index(
        "ix_content_opportunities_proj_status",
        "content_opportunities",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_content_opportunities_priority",
        "content_opportunities",
        ["project_id", "priority"],
    )


def downgrade() -> None:
    op.drop_table("content_opportunities")
    op.drop_table("keyword_page_mappings")
    op.drop_table("keyword_cluster_members")
    op.drop_table("keyword_clusters")
    op.drop_table("clustering_runs")
    op.drop_table("keyword_import_rows")
    op.drop_table("keyword_imports")
    op.drop_table("keywords")
    op.drop_table("topics")
    op.drop_table("content_pillars")
    op.drop_table("seo_strategy_versions")
    op.drop_table("seo_strategies")
