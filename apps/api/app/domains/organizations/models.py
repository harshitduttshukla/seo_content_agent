"""Organization tenant-root model."""

from datetime import datetime
from enum import StrEnum

from app.core.models import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import CheckConstraint, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended', 'archived')", name="status_allowed"),
        Index(
            "uq_organizations_active_slug",
            "slug",
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
        ),
        Index("ix_organizations_status_created", "status", "created_at"),
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=OrganizationStatus.ACTIVE
    )
    settings: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
