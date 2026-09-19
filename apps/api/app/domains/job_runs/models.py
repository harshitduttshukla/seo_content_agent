"""V3 Job Runs domain ORM model: JobRun.

V3 Reference: seo-geo-system-handoff-v3.md §3.1, §6.5, §6.8

Every model call in V3 must be traceable through JOB_RUN.
prompt_version is MANDATORY for every model call — it is NOT nullable.

Mapping:
    Existing ContentHarnessRun → V3 JobRun
    These are separate tables because ContentHarnessRun is harness-specific
    while JobRun is a universal audit log for ALL model calls.

The architecture supports later phases:
    Outline, Draft, QA Extraction, Repair, Section Regenerate
    as well as: classify, score, stale_claim_scan, auto_approve
"""

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
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class JobRunStatus(StrEnum):
    """V3: Status of a job run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """V3 §3.1: Universal model-call audit log.

    Every model call writes a JOB_RUN with:
    - prompt_version (MANDATORY — not nullable)
    - model, provider, token usage, cost
    - triggered_by to distinguish user/auto_approve/pipeline/cli/mcp
    - entity_type + entity_id for polymorphic reference to the relevant entity

    V3 §6.8 specifies five production model calls:
        1. Outline (low temp, structured)
        2. Draft (medium temp, section-chained)
        3. QA extraction (low temp, structured)
        4. Repair (medium temp)
        5. Section regenerate (medium temp)

    These are NOT implemented in Step 0 — only the audit foundation.
    """

    __tablename__ = "job_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_job_runs_org_proj_projects",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_job_runs_status_allowed",
        ),
        # Job history by type.
        Index("ix_job_runs_project_type_created", "project_id", "job_type", "created_at"),
        # Active jobs.
        Index("ix_job_runs_project_status", "project_id", "status"),
        # Entity → job lookup (polymorphic reference).
        Index("ix_job_runs_entity", "entity_type", "entity_id"),
        Index("ix_job_runs_org_proj", "organization_id", "project_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    job_type: Mapped[str] = mapped_column(String(64), nullable=False)

    # MANDATORY: prompt_version is required for every model call (V3 §6.8).
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)

    model: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)

    # Token usage and cost
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=JobRunStatus.PENDING
    )

    # Who/what triggered this job (V3 §5.4, §6.5)
    triggered_by: Mapped[str] = mapped_column(String(64), nullable=False)

    # Polymorphic entity reference — what entity is this job about?
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Job I/O — flexible structured data
    input_data: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
