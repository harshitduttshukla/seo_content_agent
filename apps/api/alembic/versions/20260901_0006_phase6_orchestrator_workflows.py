"""Phase 6 AI Orchestrator, Workflows, Steps, and Tool Executions.

Revision ID: 20260901_0006
Revises: 20260901_0005
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260901_0006"
down_revision: str | None = "20260901_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_column(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def upgrade() -> None:
    # 1. ai_workflows
    op.create_table(
        "ai_workflows",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("document_id"),
        uuid_column("created_by_id", nullable=True),
        sa.Column("intent", sa.String(64), server_default="EDIT_DOCUMENT", nullable=False),
        sa.Column("status", sa.String(32), server_default="PENDING", nullable=False),
        sa.Column("current_step", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "plan",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "error",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "token_usage",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_ai_workflows"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_ai_workflows_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["content_documents.id"],
            name="fk_ai_workflows_document_id_content_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_ai_workflows_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PLANNING', 'RUNNING', "
            "'WAITING_FOR_APPROVAL', 'COMPLETED', 'FAILED', 'CANCELLED')",
            name="ck_ai_workflows_status_allowed",
        ),
    )
    op.create_index(
        "ix_ai_workflows_proj_status",
        "ai_workflows",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_ai_workflows_doc_status",
        "ai_workflows",
        ["document_id", "status"],
    )

    # 2. ai_workflow_steps
    op.create_table(
        "ai_workflow_steps",
        uuid_column("id"),
        uuid_column("workflow_id"),
        sa.Column("step_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("step_type", sa.String(64), server_default="tool_call", nullable=False),
        sa.Column("tool_name", sa.String(64), server_default="", nullable=False),
        sa.Column("status", sa.String(32), server_default="PENDING", nullable=False),
        sa.Column(
            "input",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "output",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "error",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_ai_workflow_steps"),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["ai_workflows.id"],
            name="fk_ai_workflow_steps_workflow_id_ai_workflows",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', "
            "'FAILED', 'SKIPPED', 'WAITING_FOR_APPROVAL')",
            name="ck_ai_workflow_steps_status_allowed",
        ),
    )
    op.create_index(
        "ix_ai_workflow_steps_workflow_idx",
        "ai_workflow_steps",
        ["workflow_id", "step_index"],
    )

    # 3. tool_executions
    op.create_table(
        "tool_executions",
        uuid_column("id"),
        uuid_column("workflow_id"),
        uuid_column("step_id"),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="SUCCESS", nullable=False),
        sa.Column(
            "input",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "output",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "error",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tool_executions"),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["ai_workflows.id"],
            name="fk_tool_executions_workflow_id_ai_workflows",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["step_id"],
            ["ai_workflow_steps.id"],
            name="fk_tool_executions_step_id_ai_workflow_steps",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('SUCCESS', 'FAILED', 'REJECTED', 'TIMEOUT')",
            name="ck_tool_executions_status_allowed",
        ),
    )
    op.create_index(
        "ix_tool_executions_workflow_step",
        "tool_executions",
        ["workflow_id", "step_id"],
    )
    op.create_index(
        "ix_tool_executions_tool_name",
        "tool_executions",
        ["tool_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_tool_executions_tool_name", table_name="tool_executions")
    op.drop_index("ix_tool_executions_workflow_step", table_name="tool_executions")
    op.drop_table("tool_executions")

    op.drop_index("ix_ai_workflow_steps_workflow_idx", table_name="ai_workflow_steps")
    op.drop_table("ai_workflow_steps")

    op.drop_index("ix_ai_workflows_doc_status", table_name="ai_workflows")
    op.drop_index("ix_ai_workflows_proj_status", table_name="ai_workflows")
    op.drop_table("ai_workflows")
