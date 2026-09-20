"""V3 Content Cards domain ORM model: ContentCard.

V3 Reference: seo-geo-system-handoff-v3.md §3.1, §5.1, §5.2

The ContentCard is the central "travelling object" in V3. It travels through:
    Strategy → Content Hub → Production → Live → Iteration Lab

Mapping:
    Existing PlannedContentPage → V3 ContentCard
    These are separate tables because:
    - Incompatible state machines (7 old states vs 9 V3 states)
    - Different field sets (V3 adds market, variant_of, primary_prompt_id, etc.)
    - PlannedContentPage is preserved for backwards compatibility

V3 §5.2 State Machine:
    backlog → planned → bundled → outlined → [G1] → drafting ⇄ qa_failed
    → qa_passed → [G2] → approved → live

Origin values: plan, import, insight, manual
"""

from enum import StrEnum
from uuid import UUID

from app.core.models import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class ContentCardKind(StrEnum):
    """V3 §3.1: Content card kinds."""

    PILLAR = "pillar"
    CLUSTER = "cluster"
    COMPARE = "compare"
    REFRESH = "refresh"


class ContentCardState(StrEnum):
    """V3 §5.2: Content card production states.

    These are NOT interchangeable with the old PlannedPageStatus:
        Old: PROPOSED, PLANNED, APPROVED, IN_PROGRESS, DRAFT, PUBLISHED, ARCHIVED
        V3: backlog, planned, bundled, outlined, drafting, qa_failed, qa_passed, approved, live
    """

    BACKLOG = "backlog"
    PLANNED = "planned"
    BUNDLED = "bundled"
    OUTLINED = "outlined"
    DRAFTING = "drafting"
    QA_FAILED = "qa_failed"
    QA_PASSED = "qa_passed"
    APPROVED = "approved"
    LIVE = "live"


class ContentCardOrigin(StrEnum):
    """V3 §3.1: How a content card was created."""

    PLAN = "plan"
    IMPORT = "import"
    INSIGHT = "insight"
    MANUAL = "manual"


class ContentCard(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    """V3 §3.1: The travelling content object.

    Created in Strategy, prioritised in Content Hub, worked in Production,
    measured in the Iteration Lab. Its state machine is the Kanban.
    """

    __tablename__ = "content_cards"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_cards_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["argument_id"],
            ["arguments.id"],
            name="fk_content_cards_argument_id_arguments",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["variant_of"],
            ["content_cards.id"],
            name="fk_content_cards_variant_of_content_cards",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["primary_demand_id"],
            ["demand_nodes.id"],
            name="fk_content_cards_primary_demand_id_demand_nodes",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["primary_prompt_id"],
            ["demand_nodes.id"],
            name="fk_content_cards_primary_prompt_id_demand_nodes",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["owner"],
            ["users.id"],
            name="fk_content_cards_owner_users",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "kind IN ('pillar', 'cluster', 'compare', 'refresh')",
            name="ck_content_cards_kind_allowed",
        ),
        CheckConstraint(
            "state IN ('backlog', 'planned', 'bundled', 'outlined', 'drafting', "
            "'qa_failed', 'qa_passed', 'approved', 'live')",
            name="ck_content_cards_state_allowed",
        ),
        CheckConstraint(
            "origin IN ('plan', 'import', 'insight', 'manual')",
            name="ck_content_cards_origin_allowed",
        ),
        # Board queries: filter cards by state within a project.
        Index("ix_content_cards_project_state", "project_id", "state"),
        # Filtered views by kind.
        Index("ix_content_cards_project_kind", "project_id", "kind"),
        # Variant group lookup.
        Index("ix_content_cards_variant_of", "variant_of"),
        # Demand → card lookup.
        Index("ix_content_cards_primary_demand", "primary_demand_id"),
        # Unique slug per project (where slug is set).
        Index(
            "uq_content_cards_project_slug",
            "project_id",
            "slug",
            unique=True,
            postgresql_where="slug != ''",
        ),
        # Unique URL per project (for idempotency).
        Index(
            "uq_content_cards_project_url",
            "project_id",
            "url",
            unique=True,
            postgresql_where="url IS NOT NULL",
        ),
        Index("ix_content_cards_org_proj", "organization_id", "project_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    area_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    argument_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Market: {lang, country} — V3 §5.5
    market: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default='{"lang":"en","country":"US"}'
    )

    # Market variant relationship — V3 §5.5
    variant_of: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Demand linkage — V3 §4.7 allows dual-primary (keyword + prompt)
    primary_demand_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    primary_prompt_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    secondary_demand_ids: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    # V3 §5.2 state machine
    state: Mapped[str] = mapped_column(String(16), nullable=False, default=ContentCardState.BACKLOG)

    owner: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    due: Mapped[object | None] = mapped_column(Date, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    slug: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    # Production data — populated in later V3 steps
    outline: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    draft: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    bundle_ref: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    qa_report: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    # Publication data — V3 §6.6
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    cms_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Stale claim tracking — V3 §6.7
    stale_claims: Mapped[list[object]] = mapped_column(JSONB, nullable=False, server_default="[]")

    word_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)


class ContentCardClaim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Join table mapping ContentCards to the Claims they cite.

    Includes organization_id and project_id for tenant isolation.
    """

    __tablename__ = "content_card_claims"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_card_claims_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["content_card_id"],
            ["content_cards.id"],
            name="fk_content_card_claims_card_id_content_cards",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["claim_id"],
            ["claims.id"],
            name="fk_content_card_claims_claim_id_claims",
            ondelete="CASCADE",
        ),
        Index("uq_content_card_claims_card_claim", "content_card_id", "claim_id", unique=True),
        Index("ix_content_card_claims_claim_id", "claim_id"),  # for citation count queries
        Index("ix_content_card_claims_org_proj", "organization_id", "project_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    content_card_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    claim_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
