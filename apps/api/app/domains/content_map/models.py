"""Content Map domain database models for graph projection, layouts, and architecture versions."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from app.core.models import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import (
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


class ContentMapNodeType(StrEnum):
    PILLAR = "PILLAR"
    TOPIC = "TOPIC"
    CLUSTER = "CLUSTER"
    PAGE = "PAGE"


class ContentMapEdgeType(StrEnum):
    PILLAR_CONTAINS_TOPIC = "PILLAR_CONTAINS_TOPIC"
    TOPIC_CONTAINS_CLUSTER = "TOPIC_CONTAINS_CLUSTER"
    CLUSTER_TARGETS_PAGE = "CLUSTER_TARGETS_PAGE"
    PAGE_SUPPORTS_PAGE = "PAGE_SUPPORTS_PAGE"
    PAGE_RELATED_TO_PAGE = "PAGE_RELATED_TO_PAGE"
    PAGE_CHILD_OF_PAGE = "PAGE_CHILD_OF_PAGE"
    PAGE_LINKS_TO_PAGE = "PAGE_LINKS_TO_PAGE"
    PAGE_REFERENCES_PAGE = "PAGE_REFERENCES_PAGE"


class ContentMapNode(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "content_map_nodes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_map_nodes_org_proj_projects",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "node_type IN ('PILLAR', 'TOPIC', 'CLUSTER', 'PAGE')",
            name="ck_content_map_nodes_type_allowed",
        ),
        Index(
            "uq_content_map_nodes_proj_type_entity",
            "project_id",
            "node_type",
            "entity_id",
            unique=True,
        ),
        Index("ix_content_map_nodes_proj_type", "project_id", "node_type"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )


class ContentMapEdge(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_map_edges"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_map_edges_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_node_id"],
            ["content_map_nodes.id"],
            name="fk_content_map_edges_source_node_content_map_nodes",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_node_id"],
            ["content_map_nodes.id"],
            name="fk_content_map_edges_target_node_content_map_nodes",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "edge_type IN ('PILLAR_CONTAINS_TOPIC', 'TOPIC_CONTAINS_CLUSTER', "
            "'CLUSTER_TARGETS_PAGE', 'PAGE_SUPPORTS_PAGE', 'PAGE_RELATED_TO_PAGE', "
            "'PAGE_CHILD_OF_PAGE', 'PAGE_LINKS_TO_PAGE', 'PAGE_REFERENCES_PAGE')",
            name="ck_content_map_edges_type_allowed",
        ),
        Index(
            "uq_content_map_edges_src_tgt_type",
            "source_node_id",
            "target_node_id",
            "edge_type",
            unique=True,
        ),
        Index("ix_content_map_edges_proj_type", "project_id", "edge_type"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    edge_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_node_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    target_node_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )


class ContentArchitectureVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "content_architecture_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_arch_versions_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_arch_versions_created_by_id_users",
            ondelete="SET NULL",
        ),
        Index("uq_content_arch_versions_proj_version", "project_id", "version", unique=True),
        Index("ix_content_arch_versions_proj_created", "project_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_data: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    change_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
