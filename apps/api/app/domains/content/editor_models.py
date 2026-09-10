"""Database models for Content Briefs, Structured Documents, Chat Sessions, and AI Proposals."""

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


class BriefStatus(StrEnum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"


class DocumentStatus(StrEnum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class DocumentChangeType(StrEnum):
    INITIAL = "INITIAL"
    MANUAL_EDIT = "MANUAL_EDIT"
    AI_PATCH = "AI_PATCH"
    RESTORE = "RESTORE"
    CHECKPOINT = "CHECKPOINT"


class ProposalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    FAILED = "FAILED"


class ContentBrief(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "content_briefs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_briefs_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_content_briefs_website_id_websites",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["page_id"],
            ["planned_content_pages.id"],
            name="fk_content_briefs_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["seo_guide_id"],
            ["seo_guides.id"],
            name="fk_content_briefs_seo_guide_id_seo_guides",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_briefs_created_by_id_users",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name="fk_content_briefs_updated_by_id_users",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'PROPOSED', 'REVIEW', 'APPROVED', 'ARCHIVED')",
            name="ck_content_briefs_status_allowed",
        ),
        Index("ix_content_briefs_page_id", "page_id"),
        Index("ix_content_briefs_proj_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    website_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    page_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    seo_guide_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=BriefStatus.DRAFT)
    primary_keyword: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    secondary_keywords: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    search_intent: Mapped[str] = mapped_column(String(32), nullable=False, default="INFORMATIONAL")
    target_audience: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    business_goal: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="GUIDE")
    recommended_title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    recommended_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    meta_title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    meta_description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    target_word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1500)
    required_topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    key_entities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    questions_to_answer: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    internal_link_targets: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    external_source_requirements: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    content_requirements: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    brand_requirements: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    updated_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)


class ContentBriefVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "content_brief_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_brief_versions_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["brief_id"],
            ["content_briefs.id"],
            name="fk_content_brief_versions_brief_id_content_briefs",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_brief_versions_created_by_id_users",
            ondelete="SET NULL",
        ),
        Index("uq_content_brief_versions_version", "brief_id", "version", unique=True),
        Index("ix_content_brief_versions_proj", "project_id", "brief_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    brief_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_data: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    change_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class ContentDocument(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "content_documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_documents_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["website_id"],
            ["websites.id"],
            name="fk_content_documents_website_id_websites",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["page_id"],
            ["planned_content_pages.id"],
            name="fk_content_documents_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["brief_id"],
            ["content_briefs.id"],
            name="fk_content_documents_brief_id_content_briefs",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_documents_created_by_id_users",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name="fk_content_documents_updated_by_id_users",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'PUBLISHED', 'ARCHIVED')",
            name="ck_content_documents_status_allowed",
        ),
        Index("uq_content_documents_page_id", "page_id", unique=True),
        Index("ix_content_documents_proj_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    website_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    page_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    brief_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    slug: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=DocumentStatus.DRAFT)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_blocks: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    plain_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    updated_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)


class ContentDocumentVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "content_document_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_document_versions_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_id"],
            ["content_documents.id"],
            name="fk_content_document_versions_document_id_content_documents",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_document_versions_created_by_id_users",
            ondelete="SET NULL",
        ),
        Index("uq_content_doc_versions_doc_version", "document_id", "version", unique=True),
        Index("ix_content_doc_versions_proj", "project_id", "document_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_blocks: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    plain_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    change_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DocumentChangeType.MANUAL_EDIT
    )
    change_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class ContentChatSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "content_chat_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_chat_sessions_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_id"],
            ["content_documents.id"],
            name="fk_content_chat_sessions_document_id_content_documents",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_chat_sessions_created_by_id_users",
            ondelete="SET NULL",
        ),
        Index("ix_content_chat_sessions_doc", "document_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Chat Session")
    created_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class ContentChatMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "content_chat_messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id"],
            ["content_chat_sessions.id"],
            name="fk_content_chat_messages_session_id_content_chat_sessions",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_id"],
            ["content_documents.id"],
            name="fk_content_chat_messages_document_id_content_documents",
            ondelete="CASCADE",
        ),
        Index("ix_content_chat_messages_session_created", "session_id", "created_at"),
    )

    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # USER, ASSISTANT, SYSTEM
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    context_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    token_usage: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class AIEditProposal(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_edit_proposals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id"],
            ["content_documents.id"],
            name="fk_ai_edit_proposals_document_id_content_documents",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["chat_message_id"],
            ["content_chat_messages.id"],
            name="fk_ai_edit_proposals_chat_message_id_content_chat_messages",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["reviewed_by_id"],
            ["users.id"],
            name="fk_ai_edit_proposals_reviewed_by_id_users",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('PROPOSED', 'APPROVED', 'REJECTED', 'APPLIED', 'FAILED')",
            name="ck_ai_edit_proposals_status_allowed",
        ),
        Index("ix_ai_edit_proposals_doc_status", "document_id", "status"),
    )

    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    chat_message_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ProposalStatus.PROPOSED)
    operation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_block_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    old_content: Mapped[dict[str, object] | list[object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    proposed_content: Mapped[dict[str, object] | list[object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    diff_summary: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ai_provider: Mapped[str] = mapped_column(String(64), nullable=False, default="mock")
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
