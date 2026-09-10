"""Internal linking domain database models for page relationships and link opportunities."""

from enum import StrEnum
from uuid import UUID

from app.core.models import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class PageRelationshipType(StrEnum):
    SUPPORTS = "SUPPORTS"
    RELATED = "RELATED"
    PARENT = "PARENT"
    CHILD = "CHILD"
    COMPLEMENTARY = "COMPLEMENTARY"


class PageRelationshipStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ACTIVE = "ACTIVE"


class LinkOpportunityStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    IMPLEMENTED = "IMPLEMENTED"


class PageRelationship(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "page_relationships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_page_relationships_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_page_id"],
            ["planned_content_pages.id"],
            name="fk_page_relationships_source_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_page_id"],
            ["planned_content_pages.id"],
            name="fk_page_relationships_target_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "relationship_type IN ('SUPPORTS', 'RELATED', 'PARENT', 'CHILD', 'COMPLEMENTARY')",
            name="ck_page_relationships_type_allowed",
        ),
        CheckConstraint(
            "status IN ('PROPOSED', 'APPROVED', 'REJECTED', 'ACTIVE')",
            name="ck_page_relationships_status_allowed",
        ),
        CheckConstraint(
            "source_page_id != target_page_id",
            name="ck_page_relationships_no_self_link",
        ),
        Index(
            "uq_page_relationships_src_tgt_type",
            "source_page_id",
            "target_page_id",
            "relationship_type",
            unique=True,
        ),
        Index("ix_page_relationships_proj_status", "project_id", "status"),
        Index("ix_page_relationships_target_page", "target_page_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_page_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    target_page_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    relationship_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PageRelationshipType.SUPPORTS
    )
    anchor_text: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PageRelationshipStatus.PROPOSED
    )


class LinkOpportunity(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "link_opportunities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_link_opportunities_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_page_id"],
            ["planned_content_pages.id"],
            name="fk_link_opportunities_source_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_page_id"],
            ["planned_content_pages.id"],
            name="fk_link_opportunities_target_page_id_planned_content_pages",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('PROPOSED', 'APPROVED', 'REJECTED', 'IMPLEMENTED')",
            name="ck_link_opportunities_status_allowed",
        ),
        CheckConstraint(
            "source_page_id != target_page_id",
            name="ck_link_opportunities_no_self_link",
        ),
        Index(
            "uq_link_opportunities_proj_src_tgt",
            "project_id",
            "source_page_id",
            "target_page_id",
            unique=True,
        ),
        Index("ix_link_opportunities_proj_status", "project_id", "status"),
        Index("ix_link_opportunities_priority", "project_id", "priority"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_page_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    target_page_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    anchor_suggestion: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=LinkOpportunityStatus.PROPOSED
    )
