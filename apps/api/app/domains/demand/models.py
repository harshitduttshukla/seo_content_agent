"""V3 Demand domain ORM model: DemandNode.

V3 Reference: seo-geo-system-handoff-v3.md §3.1, §4.2, §4.5, §4.7

A DemandNode can represent a keyword OR a prompt. V3 expands the old keyword
concept into demand — prompts have their own scoring model (citation_gap ×
platforms) while keywords use volume + competitor_gap + funnel_weight.

Existing Keyword table is preserved untouched. DemandNode is a new V3 entity.

Mapping:
    Existing Keyword → V3 DemandNode (type='keyword')
    No existing equivalent → V3 DemandNode (type='prompt')
"""

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class DemandNodeType(StrEnum):
    """V3 §3.1: A demand node is either a keyword or a prompt."""

    KEYWORD = "keyword"
    PROMPT = "prompt"


class DemandNodeStatus(StrEnum):
    """V3 §4.5: Status of a demand node in the review pipeline."""

    PENDING = "pending"
    KEPT = "kept"
    DISCARDED = "discarded"


class DemandNodeOrigin(StrEnum):
    """V3 §3.1: How a demand node was created."""

    UPLOAD = "upload"
    GSC_STRIKING_DISTANCE = "gsc_striking_distance"
    INSIGHT = "insight"


class DemandNode(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    """V3 §3.1: Keyword or prompt demand node.

    Keywords are scored by: w_v * norm(volume) + w_g * competitor_gap + w_f * funnel_weight
    Prompts are scored by: citation_gap * platforms

    The volume field is nullable because prompts have no search volume.
    The citation_gap and platforms fields are only meaningful for prompts.
    """

    __tablename__ = "demand_nodes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_demand_nodes_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["argument_id"],
            ["arguments.id"],
            name="fk_demand_nodes_argument_id_arguments",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "type IN ('keyword', 'prompt')",
            name="ck_demand_nodes_type_allowed",
        ),
        CheckConstraint(
            "status IN ('pending', 'kept', 'discarded')",
            name="ck_demand_nodes_status_allowed",
        ),
        CheckConstraint(
            "origin IN ('upload', 'gsc_striking_distance', 'insight')",
            name="ck_demand_nodes_origin_allowed",
        ),
        CheckConstraint(
            "funnel IS NULL OR funnel IN ('tofu', 'mofu', 'bofu')",
            name="ck_demand_nodes_funnel_allowed",
        ),
        CheckConstraint(
            "intent IS NULL OR intent IN ('INFORMATIONAL', 'COMMERCIAL', 'TRANSACTIONAL', "
            "'NAVIGATIONAL', 'LOCAL', 'UNKNOWN')",
            name="ck_demand_nodes_intent_allowed",
        ),
        # Prevent duplicate demand: same text+type+country within a project.
        Index(
            "uq_demand_nodes_project_type_text_country",
            "project_id",
            "type",
            "text",
            "country",
            unique=True,
        ),
        # Review queue: filter by status.
        Index("ix_demand_nodes_project_status", "project_id", "status"),
        # Ranked queries by score.
        Index("ix_demand_nodes_project_type_score", "project_id", "type", "score"),
        # Demand → canvas argument lookup.
        Index("ix_demand_nodes_argument", "argument_id"),
        Index("ix_demand_nodes_org_proj", "organization_id", "project_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    type: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    variants: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")

    # Keyword-specific: nullable for prompts
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # Area reference — nullable until Area entity is created in a later step.
    area_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Canvas linkage
    argument_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    funnel: Mapped[str | None] = mapped_column(String(16), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Competitor linkage — array of competitor UUIDs (future entity)
    competitor_ids: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DemandNodeStatus.PENDING
    )
    discard_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Scoring
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_breakdown: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    origin: Mapped[str] = mapped_column(String(32), nullable=False)

    # Prompt-specific fields
    citation_gap: Mapped[float | None] = mapped_column(Float, nullable=True)
    platforms: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
