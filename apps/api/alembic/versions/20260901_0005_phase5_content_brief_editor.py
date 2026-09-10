"""Phase 5 Content Brief, Structured Document, Chat, and AI Proposals.

Revision ID: 20260901_0005
Revises: 20260901_0004
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260901_0005"
down_revision: str | None = "20260901_0004"
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
    # 1. content_briefs
    op.create_table(
        "content_briefs",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("website_id", nullable=True),
        uuid_column("page_id"),
        uuid_column("seo_guide_id", nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(32), server_default="DRAFT", nullable=False),
        sa.Column("primary_keyword", sa.String(500), server_default="", nullable=False),
        sa.Column(
            "secondary_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("search_intent", sa.String(32), server_default="INFORMATIONAL", nullable=False),
        sa.Column("target_audience", sa.String(500), server_default="", nullable=False),
        sa.Column("business_goal", sa.String(500), server_default="", nullable=False),
        sa.Column("content_type", sa.String(64), server_default="GUIDE", nullable=False),
        sa.Column("recommended_title", sa.String(500), server_default="", nullable=False),
        sa.Column("recommended_url", sa.String(2048), server_default="", nullable=False),
        sa.Column("meta_title", sa.String(500), server_default="", nullable=False),
        sa.Column("meta_description", sa.String(1000), server_default="", nullable=False),
        sa.Column("target_word_count", sa.Integer(), server_default="1500", nullable=False),
        sa.Column(
            "required_topics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "key_entities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "questions_to_answer",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "internal_link_targets",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "external_source_requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "content_requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "brand_requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        uuid_column("created_by_id", nullable=True),
        uuid_column("updated_by_id", nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PROPOSED', 'REVIEW', 'APPROVED', 'ARCHIVED')",
            name="ck_content_briefs_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_briefs_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_content_briefs_website_id_websites",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["planned_content_pages.id"],
            name="fk_content_briefs_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["seo_guide_id"],
            ["seo_guides.id"],
            name="fk_content_briefs_seo_guide_id_seo_guides",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_briefs_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name="fk_content_briefs_updated_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_briefs"),
    )
    op.create_index("ix_content_briefs_page_id", "content_briefs", ["page_id"])
    op.create_index("ix_content_briefs_proj_status", "content_briefs", ["project_id", "status"])

    # 2. content_brief_versions
    op.create_table(
        "content_brief_versions",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("brief_id"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "snapshot_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
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
            name="fk_content_brief_versions_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brief_id"],
            ["content_briefs.id"],
            name="fk_content_brief_versions_brief_id_content_briefs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_brief_versions_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_brief_versions"),
    )
    op.create_index(
        "uq_content_brief_versions_version",
        "content_brief_versions",
        ["brief_id", "version"],
        unique=True,
    )
    op.create_index(
        "ix_content_brief_versions_proj",
        "content_brief_versions",
        ["project_id", "brief_id"],
    )

    # 3. content_documents
    op.create_table(
        "content_documents",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("website_id", nullable=True),
        uuid_column("page_id"),
        uuid_column("brief_id", nullable=True),
        sa.Column("title", sa.String(500), server_default="", nullable=False),
        sa.Column("slug", sa.String(200), server_default="", nullable=False),
        sa.Column("status", sa.String(32), server_default="DRAFT", nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "content_blocks",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("plain_text", sa.Text(), server_default="", nullable=False),
        sa.Column("word_count", sa.Integer(), server_default="0", nullable=False),
        uuid_column("created_by_id", nullable=True),
        uuid_column("updated_by_id", nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'PUBLISHED', 'ARCHIVED')",
            name="ck_content_documents_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_documents_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_content_documents_website_id_websites",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["planned_content_pages.id"],
            name="fk_content_documents_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brief_id"],
            ["content_briefs.id"],
            name="fk_content_documents_brief_id_content_briefs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_documents_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name="fk_content_documents_updated_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_documents"),
    )
    op.create_index("uq_content_documents_page_id", "content_documents", ["page_id"], unique=True)
    op.create_index(
        "ix_content_documents_proj_status", "content_documents", ["project_id", "status"]
    )

    # 4. content_document_versions
    op.create_table(
        "content_document_versions",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("document_id"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "content_blocks",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("plain_text", sa.Text(), server_default="", nullable=False),
        sa.Column("word_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("change_type", sa.String(32), server_default="MANUAL_EDIT", nullable=False),
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
            name="fk_content_document_versions_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["content_documents.id"],
            name="fk_content_document_versions_document_id_content_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_document_versions_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_document_versions"),
    )
    op.create_index(
        "uq_content_doc_versions_doc_version",
        "content_document_versions",
        ["document_id", "version"],
        unique=True,
    )
    op.create_index(
        "ix_content_doc_versions_proj",
        "content_document_versions",
        ["project_id", "document_id"],
    )

    # 5. content_chat_sessions
    op.create_table(
        "content_chat_sessions",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("document_id"),
        sa.Column("title", sa.String(255), server_default="Chat Session", nullable=False),
        uuid_column("created_by_id", nullable=True),
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
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_chat_sessions_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["content_documents.id"],
            name="fk_content_chat_sessions_document_id_content_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_chat_sessions_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_chat_sessions"),
    )
    op.create_index("ix_content_chat_sessions_doc", "content_chat_sessions", ["document_id"])

    # 6. content_chat_messages
    op.create_table(
        "content_chat_messages",
        uuid_column("id"),
        uuid_column("session_id"),
        uuid_column("document_id"),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "context_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "token_usage",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["content_chat_sessions.id"],
            name="fk_content_chat_messages_session_id_content_chat_sessions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["content_documents.id"],
            name="fk_content_chat_messages_document_id_content_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_chat_messages"),
    )
    op.create_index(
        "ix_content_chat_messages_session_created",
        "content_chat_messages",
        ["session_id", "created_at"],
    )

    # 7. ai_edit_proposals
    op.create_table(
        "ai_edit_proposals",
        uuid_column("id"),
        uuid_column("document_id"),
        uuid_column("chat_message_id", nullable=True),
        sa.Column("status", sa.String(32), server_default="PROPOSED", nullable=False),
        sa.Column("operation_type", sa.String(32), nullable=False),
        sa.Column(
            "target_block_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "old_content",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "proposed_content",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "diff_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), server_default="", nullable=False),
        sa.Column("ai_provider", sa.String(64), server_default="mock", nullable=False),
        sa.Column("model", sa.String(128), server_default="default", nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        uuid_column("reviewed_by_id", nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_version", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'APPROVED', 'REJECTED', 'APPLIED', 'FAILED')",
            name="ck_ai_edit_proposals_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["content_documents.id"],
            name="fk_ai_edit_proposals_document_id_content_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chat_message_id"],
            ["content_chat_messages.id"],
            name="fk_ai_edit_proposals_chat_message_id_content_chat_messages",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_id"],
            ["users.id"],
            name="fk_ai_edit_proposals_reviewed_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_edit_proposals"),
    )
    op.create_index(
        "ix_ai_edit_proposals_doc_status", "ai_edit_proposals", ["document_id", "status"]
    )


def downgrade() -> None:
    op.drop_table("ai_edit_proposals")
    op.drop_table("content_chat_messages")
    op.drop_table("content_chat_sessions")
    op.drop_table("content_document_versions")
    op.drop_table("content_documents")
    op.drop_table("content_brief_versions")
    op.drop_table("content_briefs")
