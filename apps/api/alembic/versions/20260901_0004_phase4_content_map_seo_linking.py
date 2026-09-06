"""Phase 4 Content Map, SEO Guide, and Internal Linking Architecture.

Revision ID: 20260901_0004
Revises: 20260901_0003
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260901_0004"
down_revision: str | None = "20260901_0003"
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
    # 1. planned_content_pages
    op.create_table(
        "planned_content_pages",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("website_id", nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("url", sa.String(2048), server_default="", nullable=False),
        sa.Column("page_type", sa.String(32), server_default="PLANNED", nullable=False),
        sa.Column("content_type", sa.String(32), server_default="GUIDE", nullable=False),
        sa.Column("status", sa.String(32), server_default="PLANNED", nullable=False),
        sa.Column("intent", sa.String(32), server_default="INFORMATIONAL", nullable=False),
        sa.Column("primary_keyword", sa.String(500), server_default="", nullable=False),
        uuid_column("primary_keyword_id", nullable=True),
        uuid_column("cluster_id", nullable=True),
        uuid_column("topic_id", nullable=True),
        uuid_column("pillar_id", nullable=True),
        sa.Column("priority", sa.Integer(), server_default="1", nullable=False),
        sa.Column("business_value", sa.Float(), server_default="0.0", nullable=False),
        uuid_column("existing_page_id", nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "page_type IN ('EXISTING', 'PLANNED', 'IMPORTED', 'REDIRECTED')",
            name="ck_planned_content_pages_page_type_allowed",
        ),
        sa.CheckConstraint(
            "content_type IN ('PILLAR_PAGE', 'CLUSTER_PAGE', 'SUPPORTING_PAGE', "
            "'LANDING_PAGE', 'SERVICE_PAGE', 'PRODUCT_PAGE', 'BLOG_POST', "
            "'GUIDE', 'COMPARISON', 'FAQ')",
            name="ck_planned_content_pages_content_type_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'PLANNED', 'APPROVED', 'IN_PROGRESS', "
            "'DRAFT', 'PUBLISHED', 'ARCHIVED')",
            name="ck_planned_content_pages_status_allowed",
        ),
        sa.CheckConstraint(
            "intent IN ('INFORMATIONAL', 'COMMERCIAL', 'TRANSACTIONAL', "
            "'NAVIGATIONAL', 'LOCAL', 'UNKNOWN')",
            name="ck_planned_content_pages_intent_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_planned_content_pages_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_planned_content_pages_website_id_websites",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["existing_page_id"],
            ["content_pages.id"],
            name="fk_planned_content_pages_existing_page_id_content_pages",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["keyword_clusters.id"],
            name="fk_planned_content_pages_cluster_id_keyword_clusters",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name="fk_planned_content_pages_topic_id_topics",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["pillar_id"],
            ["content_pillars.id"],
            name="fk_planned_content_pages_pillar_id_content_pillars",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["primary_keyword_id"],
            ["keywords.id"],
            name="fk_planned_content_pages_primary_kw_keywords",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_planned_content_pages"),
    )
    op.create_index(
        "uq_planned_content_pages_proj_slug",
        "planned_content_pages",
        ["project_id", "slug"],
        unique=True,
    )
    op.create_index(
        "ix_planned_content_pages_proj_status",
        "planned_content_pages",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_planned_content_pages_cluster",
        "planned_content_pages",
        ["cluster_id"],
    )
    op.create_index(
        "ix_planned_content_pages_topic",
        "planned_content_pages",
        ["topic_id"],
    )
    op.create_index(
        "ix_planned_content_pages_pillar",
        "planned_content_pages",
        ["pillar_id"],
    )

    # 2. page_keywords
    op.create_table(
        "page_keywords",
        uuid_column("id"),
        uuid_column("page_id"),
        uuid_column("keyword_id"),
        sa.Column("keyword_role", sa.String(32), server_default="SECONDARY", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "keyword_role IN ('PRIMARY', 'SECONDARY', 'RELATED')",
            name="ck_page_keywords_role_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["planned_content_pages.id"],
            name="fk_page_keywords_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["keyword_id"],
            ["keywords.id"],
            name="fk_page_keywords_keyword_id_keywords",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_page_keywords"),
    )
    op.create_index(
        "uq_page_keywords_page_keyword",
        "page_keywords",
        ["page_id", "keyword_id"],
        unique=True,
    )
    op.create_index("ix_page_keywords_kw_id", "page_keywords", ["keyword_id"])
    op.create_index("ix_page_keywords_page_role", "page_keywords", ["page_id", "keyword_role"])

    # 3. content_map_nodes
    op.create_table(
        "content_map_nodes",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        sa.Column("node_type", sa.String(32), nullable=False),
        uuid_column("entity_id"),
        sa.Column("label", sa.String(255), server_default="", nullable=False),
        sa.Column("position_x", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("position_y", sa.Float(), server_default="0.0", nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "node_type IN ('PILLAR', 'TOPIC', 'CLUSTER', 'PAGE')",
            name="ck_content_map_nodes_type_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_map_nodes_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_map_nodes"),
    )
    op.create_index(
        "uq_content_map_nodes_proj_type_entity",
        "content_map_nodes",
        ["project_id", "node_type", "entity_id"],
        unique=True,
    )
    op.create_index(
        "ix_content_map_nodes_proj_type",
        "content_map_nodes",
        ["project_id", "node_type"],
    )

    # 4. content_map_edges
    op.create_table(
        "content_map_edges",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        sa.Column("edge_type", sa.String(64), nullable=False),
        uuid_column("source_node_id"),
        uuid_column("target_node_id"),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *timestamps(),
        sa.CheckConstraint(
            "edge_type IN ('PILLAR_CONTAINS_TOPIC', 'TOPIC_CONTAINS_CLUSTER', "
            "'CLUSTER_TARGETS_PAGE', 'PAGE_SUPPORTS_PAGE', 'PAGE_RELATED_TO_PAGE', "
            "'PAGE_CHILD_OF_PAGE', 'PAGE_LINKS_TO_PAGE', 'PAGE_REFERENCES_PAGE')",
            name="ck_content_map_edges_type_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_map_edges_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_node_id"],
            ["content_map_nodes.id"],
            name="fk_content_map_edges_source_node_content_map_nodes",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_node_id"],
            ["content_map_nodes.id"],
            name="fk_content_map_edges_target_node_content_map_nodes",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_map_edges"),
    )
    op.create_index(
        "uq_content_map_edges_src_tgt_type",
        "content_map_edges",
        ["source_node_id", "target_node_id", "edge_type"],
        unique=True,
    )
    op.create_index(
        "ix_content_map_edges_proj_type",
        "content_map_edges",
        ["project_id", "edge_type"],
    )

    # 5. content_architecture_versions
    op.create_table(
        "content_architecture_versions",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "snapshot_data",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("change_summary", sa.Text(), server_default="", nullable=False),
        uuid_column("created_by_id", nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_arch_versions_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_arch_versions_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_architecture_versions"),
    )
    op.create_index(
        "uq_content_arch_versions_proj_version",
        "content_architecture_versions",
        ["project_id", "version"],
        unique=True,
    )
    op.create_index(
        "ix_content_arch_versions_proj_created",
        "content_architecture_versions",
        ["project_id", "created_at"],
    )

    # 6. seo_guides
    op.create_table(
        "seo_guides",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("page_id"),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(32), server_default="draft", nullable=False),
        sa.Column("primary_keyword", sa.String(500), server_default="", nullable=False),
        sa.Column(
            "secondary_keywords",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("search_intent", sa.String(32), server_default="INFORMATIONAL", nullable=False),
        sa.Column("target_audience", sa.String(500), server_default="", nullable=False),
        sa.Column("recommended_title", sa.String(500), server_default="", nullable=False),
        sa.Column("meta_title", sa.String(500), server_default="", nullable=False),
        sa.Column("meta_description", sa.String(1000), server_default="", nullable=False),
        sa.Column("recommended_url", sa.String(2048), server_default="", nullable=False),
        sa.Column("content_type", sa.String(32), server_default="GUIDE", nullable=False),
        sa.Column("word_count_target", sa.Integer(), server_default="1500", nullable=False),
        sa.Column(
            "required_topics",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "key_entities",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("serp_notes", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "content_requirements",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "outline",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "seo_rules",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'active', 'archived')",
            name="ck_seo_guides_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_seo_guides_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["planned_content_pages.id"],
            name="fk_seo_guides_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_seo_guides"),
    )
    op.create_index("uq_seo_guides_page_id", "seo_guides", ["page_id"], unique=True)
    op.create_index(
        "ix_seo_guides_proj_status",
        "seo_guides",
        ["project_id", "status"],
    )

    # 7. seo_guide_versions
    op.create_table(
        "seo_guide_versions",
        uuid_column("id"),
        uuid_column("guide_id"),
        uuid_column("page_id"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "snapshot_data",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("change_summary", sa.Text(), server_default="", nullable=False),
        uuid_column("created_by_id", nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["guide_id"],
            ["seo_guides.id"],
            name="fk_seo_guide_versions_guide_id_seo_guides",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_seo_guide_versions_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_seo_guide_versions"),
    )
    op.create_index(
        "uq_seo_guide_versions_guide_version",
        "seo_guide_versions",
        ["guide_id", "version"],
        unique=True,
    )
    op.create_index(
        "ix_seo_guide_versions_page_id",
        "seo_guide_versions",
        ["page_id"],
    )

    # 8. page_relationships
    op.create_table(
        "page_relationships",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("source_page_id"),
        uuid_column("target_page_id"),
        sa.Column("relationship_type", sa.String(32), server_default="SUPPORTS", nullable=False),
        sa.Column("anchor_text", sa.String(500), server_default="", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="1", nullable=False),
        sa.Column("reason", sa.Text(), server_default="", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("status", sa.String(32), server_default="PROPOSED", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "relationship_type IN ('SUPPORTS', 'RELATED', 'PARENT', 'CHILD', 'COMPLEMENTARY')",
            name="ck_page_relationships_type_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'APPROVED', 'REJECTED', 'ACTIVE')",
            name="ck_page_relationships_status_allowed",
        ),
        sa.CheckConstraint(
            "source_page_id != target_page_id",
            name="ck_page_relationships_no_self_link",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_page_relationships_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_page_id"],
            ["planned_content_pages.id"],
            name="fk_page_relationships_source_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_page_id"],
            ["planned_content_pages.id"],
            name="fk_page_relationships_target_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_page_relationships"),
    )
    op.create_index(
        "uq_page_relationships_src_tgt_type",
        "page_relationships",
        ["source_page_id", "target_page_id", "relationship_type"],
        unique=True,
    )
    op.create_index(
        "ix_page_relationships_proj_status",
        "page_relationships",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_page_relationships_target_page",
        "page_relationships",
        ["target_page_id"],
    )

    # 9. link_opportunities
    op.create_table(
        "link_opportunities",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("source_page_id"),
        uuid_column("target_page_id"),
        sa.Column("source_url", sa.String(2048), server_default="", nullable=False),
        sa.Column("target_url", sa.String(2048), server_default="", nullable=False),
        sa.Column("anchor_suggestion", sa.String(500), server_default="", nullable=False),
        sa.Column("reason", sa.Text(), server_default="", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(32), server_default="PROPOSED", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'APPROVED', 'REJECTED', 'IMPLEMENTED')",
            name="ck_link_opportunities_status_allowed",
        ),
        sa.CheckConstraint(
            "source_page_id != target_page_id",
            name="ck_link_opportunities_no_self_link",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_link_opportunities_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_page_id"],
            ["planned_content_pages.id"],
            name="fk_link_opportunities_source_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_page_id"],
            ["planned_content_pages.id"],
            name="fk_link_opportunities_target_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_link_opportunities"),
    )
    op.create_index(
        "uq_link_opportunities_proj_src_tgt",
        "link_opportunities",
        ["project_id", "source_page_id", "target_page_id"],
        unique=True,
    )
    op.create_index(
        "ix_link_opportunities_proj_status",
        "link_opportunities",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_link_opportunities_priority",
        "link_opportunities",
        ["project_id", "priority"],
    )


def downgrade() -> None:
    op.drop_table("link_opportunities")
    op.drop_table("page_relationships")
    op.drop_table("seo_guide_versions")
    op.drop_table("seo_guides")
    op.drop_table("content_architecture_versions")
    op.drop_table("content_map_edges")
    op.drop_table("content_map_nodes")
    op.drop_table("page_keywords")
    op.drop_table("planned_content_pages")
