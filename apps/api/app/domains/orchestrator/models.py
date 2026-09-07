"""Database models for AI Orchestrator Workflows, Workflow Steps, and Tool Executions."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class WorkflowIntent(StrEnum):
    EDIT_DOCUMENT = "EDIT_DOCUMENT"
    ANALYZE_SEO = "ANALYZE_SEO"
    GENERATE_OUTLINE = "GENERATE_OUTLINE"
    RESEARCH_TOPIC = "RESEARCH_TOPIC"
    FIND_INTERNAL_LINKS = "FIND_INTERNAL_LINKS"
    OPTIMIZE_METADATA = "OPTIMIZE_METADATA"
    ANALYZE_CONTENT = "ANALYZE_CONTENT"
    MULTI_STEP_CONTENT_TASK = "MULTI_STEP_CONTENT_TASK"


class WorkflowStatus(StrEnum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"


class ToolExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"


class AIWorkflow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_workflows"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_ai_workflows_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_id"],
            ["content_documents.id"],
            name="fk_ai_workflows_document_id_content_documents",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_ai_workflows_created_by_id_users",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PLANNING', 'RUNNING', 'WAITING_FOR_APPROVAL', "
            "'COMPLETED', 'FAILED', 'CANCELLED')",
            name="ck_ai_workflows_status_allowed",
        ),
        Index("ix_ai_workflows_proj_status", "project_id", "status"),
        Index("ix_ai_workflows_doc_status", "document_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    intent: Mapped[str] = mapped_column(
        String(64), nullable=False, default=WorkflowIntent.EDIT_DOCUMENT
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=WorkflowStatus.PENDING)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plan: Mapped[dict[str, object] | list[object]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    result: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, server_default="{}")
    error: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    token_usage: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIWorkflowStep(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_workflow_steps"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_id"],
            ["ai_workflows.id"],
            name="fk_ai_workflow_steps_workflow_id_ai_workflows",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED', "
            "'WAITING_FOR_APPROVAL')",
            name="ck_ai_workflow_steps_status_allowed",
        ),
        Index("ix_ai_workflow_steps_workflow_idx", "workflow_id", "step_index"),
    )

    workflow_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    step_type: Mapped[str] = mapped_column(String(64), nullable=False, default="tool_call")
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=StepStatus.PENDING)
    input: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, server_default="{}")
    output: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, server_default="{}")
    error: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ToolExecutionRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "tool_executions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_id"],
            ["ai_workflows.id"],
            name="fk_tool_executions_workflow_id_ai_workflows",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["step_id"],
            ["ai_workflow_steps.id"],
            name="fk_tool_executions_step_id_ai_workflow_steps",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('SUCCESS', 'FAILED', 'REJECTED', 'TIMEOUT')",
            name="ck_tool_executions_status_allowed",
        ),
        Index("ix_tool_executions_workflow_step", "workflow_id", "step_id"),
        Index("ix_tool_executions_tool_name", "tool_name"),
    )

    workflow_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    step_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ToolExecutionStatus.SUCCESS
    )
    input: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, server_default="{}")
    output: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, server_default="{}")
    error: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
