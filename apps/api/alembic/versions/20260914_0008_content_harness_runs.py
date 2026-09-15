"""Content Harness Runs storage table.

Revision ID: 20260914_0008
Revises: 20260910_0007
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260914_0008"
down_revision: str | None = "20260910_0007"
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
    op.create_table(
        "content_harness_runs",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("created_by_id", nullable=True),
        sa.Column("name", sa.String(255), server_default="Content Harness Run", nullable=False),
        sa.Column("status", sa.String(32), server_default="PENDING", nullable=False),
        sa.Column("prompt_version", sa.String(64), server_default="v1", nullable=False),
        sa.Column("model", sa.String(128), server_default="gemini-flash-latest", nullable=False),
        sa.Column("provider", sa.String(64), server_default="mock", nullable=False),
        sa.Column(
            "input_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "context_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "prompt_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "output_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "evaluation_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_content_harness_runs"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_harness_runs_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_content_harness_runs_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_content_harness_runs_status_allowed",
        ),
    )
    op.create_index(
        "ix_content_harness_runs_proj_created",
        "content_harness_runs",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_content_harness_runs_proj_status",
        "content_harness_runs",
        ["project_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_content_harness_runs_proj_status", table_name="content_harness_runs")
    op.drop_index("ix_content_harness_runs_proj_created", table_name="content_harness_runs")
    op.drop_table("content_harness_runs")
