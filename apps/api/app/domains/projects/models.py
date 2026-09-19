"""Project aggregate-root model."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.core.models import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Project(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        CheckConstraint("status IN ('active', 'archived')", name="status_allowed"),
        Index(
            "uq_projects_active_org_slug",
            "organization_id",
            "slug",
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
        ),
        Index("ix_projects_org_status_created", "organization_id", "status", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(2_000), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ProjectStatus.ACTIVE)
    default_locale: Mapped[str] = mapped_column(String(20), nullable=False, default="en")
    default_country: Mapped[str | None] = mapped_column(String(2))
    settings: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)

    # V3 9.2: Typed workspace configuration (scoring weights, funnel definitions,
    # word budgets, markets, auto-approval, etc.). Separate from `settings` to keep
    # V3 config isolated and schema-validated via WorkspaceConfig Pydantic model.
    workspace_config: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
