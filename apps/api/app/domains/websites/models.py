"""Project-owned website identity model."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.core.models import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class WebsiteStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class Website(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "websites"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="CASCADE",
        ),
        # Lets project-owned rows reference a website together with its tenant.
        UniqueConstraint("organization_id", "project_id", "id", name="uq_websites_org_proj_id"),
        CheckConstraint("status IN ('active', 'inactive', 'archived')", name="status_allowed"),
        CheckConstraint(
            "verification_status IN ('unverified', 'verified', 'failed')",
            name="verification_status_allowed",
        ),
        Index(
            "uq_websites_active_project_host_locale",
            "project_id",
            "normalized_host",
            "locale",
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
        ),
        Index("ix_websites_org_project_status", "organization_id", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2_048), nullable=False)
    normalized_host: Mapped[str] = mapped_column(String(253), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=WebsiteStatus.ACTIVE)
    locale: Mapped[str] = mapped_column(String(20), nullable=False, default="en")
    country: Mapped[str | None] = mapped_column(String(2))
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unverified"
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settings: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
