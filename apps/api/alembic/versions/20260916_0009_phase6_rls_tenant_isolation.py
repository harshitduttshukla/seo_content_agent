"""Phase 6 RLS tenant isolation and composite workflow→document ownership.

Adds Row Level Security policies to Phase 5/6 tenant-owned tables as
defense-in-depth.  Also adds a composite FK enforcing that a workflow's
organization_id/project_id/document_id triplet is consistent with
content_documents.

Revision ID: 20260916_0009
Revises: 20260914_0008
Create Date: 2026-09-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260916_0009"
down_revision: str | None = "20260914_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ──────────────────────────────────────────────────────────────────
# Tables that directly own organization_id + project_id
# ──────────────────────────────────────────────────────────────────
_DIRECT_PROJECT_TABLES = ("content_documents", "ai_workflows")

# ──────────────────────────────────────────────────────────────────
# Child tables scoped through a parent FK
# ──────────────────────────────────────────────────────────────────
_CHILD_TABLES: list[tuple[str, str, str]] = [
    # (table, parent_fk_column, parent_table)
    ("ai_workflow_steps", "workflow_id", "ai_workflows"),
    ("tool_executions", "workflow_id", "ai_workflows"),
    ("ai_edit_proposals", "document_id", "content_documents"),
]


def upgrade() -> None:
    # ── 1. Enable RLS on all target tables ───────────────────────
    for table in _DIRECT_PROJECT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    for table, _, _ in _CHILD_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    # ── 2. Direct project-scoped policies ────────────────────────
    # Follow the Phase-1 pattern: single combined policy using
    # app_has_project_access() for USING and WITH CHECK.
    for table in _DIRECT_PROJECT_TABLES:
        op.execute(
            f"""CREATE POLICY {table}_tenant_all ON {table}
            USING (app_has_project_access(organization_id, project_id))
            WITH CHECK (app_has_project_access(organization_id, project_id))"""
        )

    # ── 3. Child-table policies via parent subquery ──────────────
    # ai_workflow_steps → ai_workflows
    op.execute(
        """CREATE POLICY ai_workflow_steps_tenant_all ON ai_workflow_steps
        USING (EXISTS (
            SELECT 1 FROM ai_workflows w
            WHERE w.id = ai_workflow_steps.workflow_id
              AND app_has_project_access(w.organization_id, w.project_id)
        ))
        WITH CHECK (EXISTS (
            SELECT 1 FROM ai_workflows w
            WHERE w.id = ai_workflow_steps.workflow_id
              AND app_has_project_access(w.organization_id, w.project_id)
        ))"""
    )

    # tool_executions → ai_workflows
    op.execute(
        """CREATE POLICY tool_executions_tenant_all ON tool_executions
        USING (EXISTS (
            SELECT 1 FROM ai_workflows w
            WHERE w.id = tool_executions.workflow_id
              AND app_has_project_access(w.organization_id, w.project_id)
        ))
        WITH CHECK (EXISTS (
            SELECT 1 FROM ai_workflows w
            WHERE w.id = tool_executions.workflow_id
              AND app_has_project_access(w.organization_id, w.project_id)
        ))"""
    )

    # ai_edit_proposals → content_documents
    op.execute(
        """CREATE POLICY ai_edit_proposals_tenant_all ON ai_edit_proposals
        USING (EXISTS (
            SELECT 1 FROM content_documents d
            WHERE d.id = ai_edit_proposals.document_id
              AND app_has_project_access(d.organization_id, d.project_id)
        ))
        WITH CHECK (EXISTS (
            SELECT 1 FROM content_documents d
            WHERE d.id = ai_edit_proposals.document_id
              AND app_has_project_access(d.organization_id, d.project_id)
        ))"""
    )

    # ── 4. Grant to application role (matches Phase-1 pattern) ───
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'seo_content_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON
              content_documents, ai_workflows, ai_workflow_steps,
              tool_executions, ai_edit_proposals
            TO seo_content_app;
          END IF;
        END $$
        """
    )

    # ── 5. Composite unique constraint on content_documents ──────
    # Required as the target of the composite FK from ai_workflows.
    op.create_unique_constraint(
        "uq_content_documents_org_proj_id",
        "content_documents",
        ["organization_id", "project_id", "id"],
    )

    # ── 6. Drop the existing simple document FK on ai_workflows ──
    op.drop_constraint(
        "fk_ai_workflows_document_id_content_documents",
        "ai_workflows",
        type_="foreignkey",
    )

    # ── 7. Add composite FK enforcing ownership consistency ──────
    op.create_foreign_key(
        "fk_ai_workflows_org_proj_doc_content_documents",
        "ai_workflows",
        "content_documents",
        ["organization_id", "project_id", "document_id"],
        ["organization_id", "project_id", "id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # ── Reverse composite FK ─────────────────────────────────────
    op.drop_constraint(
        "fk_ai_workflows_org_proj_doc_content_documents",
        "ai_workflows",
        type_="foreignkey",
    )

    # ── Restore simple document FK ───────────────────────────────
    op.create_foreign_key(
        "fk_ai_workflows_document_id_content_documents",
        "ai_workflows",
        "content_documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ── Drop composite unique constraint ─────────────────────────
    op.drop_constraint(
        "uq_content_documents_org_proj_id",
        "content_documents",
        type_="unique",
    )

    # ── Drop RLS policies ────────────────────────────────────────
    policies = (
        ("content_documents", "content_documents_tenant_all"),
        ("ai_workflows", "ai_workflows_tenant_all"),
        ("ai_workflow_steps", "ai_workflow_steps_tenant_all"),
        ("tool_executions", "tool_executions_tenant_all"),
        ("ai_edit_proposals", "ai_edit_proposals_tenant_all"),
    )
    for table, policy in policies:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")

    # ── Disable RLS ──────────────────────────────────────────────
    for table, _, _ in reversed(_CHILD_TABLES):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for table in reversed(_DIRECT_PROJECT_TABLES):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
