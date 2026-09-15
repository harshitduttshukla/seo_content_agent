"""Database model for Content Harness Runs."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class HarnessRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ContentHarnessRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_harness_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_harness_runs_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_harness_runs_created_by_id_users",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_content_harness_runs_status_allowed",
        ),
        Index("ix_content_harness_runs_proj_created", "project_id", "created_at"),
        Index("ix_content_harness_runs_proj_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Content Harness Run",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=HarnessRunStatus.PENDING.value,
    )
    prompt_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="v1",
    )
    model: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="gemini-flash-latest",
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="mock",
    )
    input_data: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    context_data: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    prompt_data: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    output_data: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    evaluation_data: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
