"""V3 Canvas domain ORM models: Canvas, Argument, Area, Claim.

V3 Reference: seo-geo-system-handoff-v3.md §3.1, §4.1

Canvas represents a Fletch positioning canvas.
- Company-level canvas: parent_id IS NULL
- Product-line canvas: parent_id references the company canvas

Argument represents one column of the canvas:
  sub_problem → differentiation_pillar → capability → features → benefit

Claim represents one approved canvas cell, addressable as [CLM-xxx]:
  Each claim is independently versioned via superseded_by chain.
"""

from enum import StrEnum
from uuid import UUID

from app.core.models import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import (
    Boolean,
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


class ClaimRow(StrEnum):
    """V3 §3.1: Valid row types for a Claim cell."""

    SUB_PROBLEM = "sub_problem"
    PILLAR = "pillar"
    CAPABILITY = "capability"
    FEATURE = "feature"
    BENEFIT = "benefit"
    PROBLEM_SUMMARY = "problem_summary"
    DIFFERENTIATION_SUMMARY = "differentiation_summary"
    PITCH = "pitch"


class Canvas(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    """V3 §3.1: One Fletch positioning canvas.

    Company canvas: parent_id IS NULL, product_line IS NULL.
    Product-line canvas: parent_id → company canvas, product_line set.

    Anchors (company, persona, use_case, alternative, category) are stored
    as JSONB with {text, primary} structure per V3 §3.1.
    """

    __tablename__ = "canvases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_canvases_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["parent_id"],
            ["canvases.id"],
            name="fk_canvases_parent_id_canvases",
            ondelete="RESTRICT",
        ),
        # A product-line canvas must have a product_line name.
        CheckConstraint(
            "parent_id IS NULL OR product_line IS NOT NULL",
            name="ck_canvases_product_line_required_for_child",
        ),
        # Unique product_line name within a project (for non-null product_lines).
        Index(
            "uq_canvases_project_product_line",
            "project_id",
            "product_line",
            unique=True,
            postgresql_where="product_line IS NOT NULL",
        ),
        # At most one company canvas (parent_id IS NULL) per project.
        Index(
            "uq_canvases_project_company",
            "project_id",
            unique=True,
            postgresql_where="parent_id IS NULL",
        ),
        Index("ix_canvases_org_proj", "organization_id", "project_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    product_line: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Anchors: each is {text: str, primary: bool}
    company_anchor: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    persona_anchor: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    use_case_anchor: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    alternative_anchor: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    category_anchor: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    problem_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    differentiation_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Argument(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    """V3 §3.1: One argument column of a canvas.

    Structure: sub_problem → differentiation_pillar → capability → features → benefit.

    Inheritance: inherited_from references the parent canvas's argument that
    this argument was derived from. override=True means the product canvas
    explicitly overrides the inherited values.
    """

    __tablename__ = "arguments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_arguments_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["canvas_id"],
            ["canvases.id"],
            name="fk_arguments_canvas_id_canvases",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["inherited_from"],
            ["arguments.id"],
            name="fk_arguments_inherited_from_arguments",
            ondelete="SET NULL",
        ),
        # Unique order per canvas.
        Index("uq_arguments_canvas_order", "canvas_id", "order", unique=True),
        Index("ix_arguments_org_proj", "organization_id", "project_id"),
        Index("ix_arguments_canvas", "canvas_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    canvas_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sub_problem: Mapped[str] = mapped_column(Text, nullable=False, default="")
    differentiation_pillar: Mapped[str] = mapped_column(Text, nullable=False, default="")
    capability: Mapped[str] = mapped_column(Text, nullable=False, default="")
    features: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    benefit: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Inheritance tracking
    inherited_from: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Area(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    """V3 §3.1: A named node in a Canvas-scoped product tree."""

    __tablename__ = "areas"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_areas_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["canvas_id"],
            ["canvases.id"],
            name="fk_areas_canvas_id_canvases",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["parent_id"],
            ["areas.id"],
            name="fk_areas_parent_id_areas",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["default_argument_id"],
            ["arguments.id"],
            name="fk_areas_default_argument_id_arguments",
            ondelete="SET NULL",
        ),
        Index("ix_areas_org_proj", "organization_id", "project_id"),
        Index("ix_areas_canvas", "canvas_id"),
        Index("ix_areas_parent", "parent_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    canvas_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    default_argument_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)


class Claim(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    """V3 §3.1: One approved canvas cell, independently addressable.

    Claims are the core traceability mechanism in V3. Every brand assertion
    in produced content must reference an approved claim.

    Versioning: when a claim is updated, a new Claim row is created and
    the old row's superseded_by is set to the new row's id. The current
    version is the one where superseded_by IS NULL.

    Row types correspond to canvas structure positions per V3 §3.1.
    """

    __tablename__ = "claims"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_claims_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["canvas_id"],
            ["canvases.id"],
            name="fk_claims_canvas_id_canvases",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["argument_id"],
            ["arguments.id"],
            name="fk_claims_argument_id_arguments",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["approved_by"],
            ["users.id"],
            name="fk_claims_approved_by_users",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["superseded_by"],
            ["claims.id"],
            name="fk_claims_superseded_by_claims",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "row IN ('sub_problem', 'pillar', 'capability', 'feature', 'benefit', "
            "'problem_summary', 'differentiation_summary', 'pitch')",
            name="ck_claims_row_allowed",
        ),
        # Content/production lookup: find claims by canvas position.
        Index("ix_claims_canvas_argument_row", "canvas_id", "argument_id", "row"),
        # Coverage queries: find all approved claims in a project.
        Index("ix_claims_project_approved", "project_id", "approved"),
        # Version chain traversal.
        Index("ix_claims_superseded_by", "superseded_by"),
        Index("ix_claims_org_proj", "organization_id", "project_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    canvas_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    argument_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    row: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="")

    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    approved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    superseded_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Per-market overrides: {market_key: {text, evidence}} — V3 §5.5
    market_overrides: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
