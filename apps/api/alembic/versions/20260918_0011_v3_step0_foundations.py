"""V3 Step 0: Foundations & Data Models.

Creates the foundational V3 entities as additive, non-breaking schema changes:
- workspace_config column on projects
- canvases table (Canvas)
- arguments table (Argument)
- claims table (Claim)
- demand_nodes table (DemandNode)
- content_cards table (ContentCard)
- job_runs table (JobRun)

Enables RLS on all new tables using the existing app_has_project_access() function.

V3 Reference: seo-geo-system-handoff-v3.md §3.1, §5.2, §6.8, §9.2

Revision ID: 20260918_0011
Revises: 20260916_0010
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260918_0011"
down_revision: str | None = "20260916_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that carry organization_id + project_id directly.
_PROJECT_SCOPED_TABLES = (
    "canvases",
    "arguments",
    "claims",
    "demand_nodes",
    "content_cards",
    "job_runs",
)


def upgrade() -> None:
    # ── 1. Add workspace_config column to projects ──────────────
    op.add_column(
        "projects",
        sa.Column(
            "workspace_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )

    # ── 2. Create canvases table ────────────────────────────────
    op.create_table(
        "canvases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_line", sa.String(200), nullable=True),
        sa.Column(
            "company_anchor",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "persona_anchor",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "use_case_anchor",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "alternative_anchor",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "category_anchor",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("problem_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("differentiation_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_canvases_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["canvases.id"],
            name="fk_canvases_parent_id_canvases",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR product_line IS NOT NULL",
            name="ck_canvases_product_line_required_for_child",
        ),
    )
    op.create_index(
        "uq_canvases_project_product_line",
        "canvases",
        ["project_id", "product_line"],
        unique=True,
        postgresql_where=sa.text("product_line IS NOT NULL"),
    )
    op.create_index(
        "uq_canvases_project_company",
        "canvases",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL"),
    )
    op.create_index("ix_canvases_org_proj", "canvases", ["organization_id", "project_id"])

    # ── 3. Create arguments table ───────────────────────────────
    op.create_table(
        "arguments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canvas_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sub_problem", sa.Text(), nullable=False, server_default=""),
        sa.Column("differentiation_pillar", sa.Text(), nullable=False, server_default=""),
        sa.Column("capability", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "features",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("benefit", sa.Text(), nullable=False, server_default=""),
        sa.Column("inherited_from", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("override", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_arguments_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["canvas_id"],
            ["canvases.id"],
            name="fk_arguments_canvas_id_canvases",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["inherited_from"],
            ["arguments.id"],
            name="fk_arguments_inherited_from_arguments",
            ondelete="SET NULL",
        ),
    )
    op.create_index("uq_arguments_canvas_order", "arguments", ["canvas_id", "order"], unique=True)
    op.create_index("ix_arguments_org_proj", "arguments", ["organization_id", "project_id"])
    op.create_index("ix_arguments_canvas", "arguments", ["canvas_id"])

    # ── 4. Create claims table ──────────────────────────────────
    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canvas_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("argument_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("row", sa.String(40), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "market_overrides",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_claims_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["canvas_id"],
            ["canvases.id"],
            name="fk_claims_canvas_id_canvases",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["argument_id"],
            ["arguments.id"],
            name="fk_claims_argument_id_arguments",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["users.id"],
            name="fk_claims_approved_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by"],
            ["claims.id"],
            name="fk_claims_superseded_by_claims",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "row IN ('sub_problem', 'pillar', 'capability', 'feature', 'benefit', "
            "'problem_summary', 'differentiation_summary', 'pitch')",
            name="ck_claims_row_allowed",
        ),
    )
    op.create_index(
        "ix_claims_canvas_argument_row", "claims", ["canvas_id", "argument_id", "row"]
    )
    op.create_index("ix_claims_project_approved", "claims", ["project_id", "approved"])
    op.create_index("ix_claims_superseded_by", "claims", ["superseded_by"])
    op.create_index("ix_claims_org_proj", "claims", ["organization_id", "project_id"])

    # ── 5. Create demand_nodes table ────────────────────────────
    op.create_table(
        "demand_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "variants",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("argument_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("funnel", sa.String(16), nullable=True),
        sa.Column("intent", sa.String(32), nullable=True),
        sa.Column(
            "competitor_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("discard_reason", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("score_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("origin", sa.String(32), nullable=False),
        sa.Column("citation_gap", sa.Float(), nullable=True),
        sa.Column(
            "platforms",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_demand_nodes_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["argument_id"],
            ["arguments.id"],
            name="fk_demand_nodes_argument_id_arguments",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "type IN ('keyword', 'prompt')",
            name="ck_demand_nodes_type_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'kept', 'discarded')",
            name="ck_demand_nodes_status_allowed",
        ),
        sa.CheckConstraint(
            "origin IN ('upload', 'gsc_striking_distance', 'insight')",
            name="ck_demand_nodes_origin_allowed",
        ),
        sa.CheckConstraint(
            "funnel IS NULL OR funnel IN ('tofu', 'mofu', 'bofu')",
            name="ck_demand_nodes_funnel_allowed",
        ),
        sa.CheckConstraint(
            "intent IS NULL OR intent IN ('INFORMATIONAL', 'COMMERCIAL', 'TRANSACTIONAL', "
            "'NAVIGATIONAL', 'LOCAL', 'UNKNOWN')",
            name="ck_demand_nodes_intent_allowed",
        ),
    )
    op.create_index(
        "uq_demand_nodes_project_type_text_country",
        "demand_nodes",
        ["project_id", "type", "text", "country"],
        unique=True,
    )
    op.create_index(
        "ix_demand_nodes_project_status", "demand_nodes", ["project_id", "status"]
    )
    op.create_index(
        "ix_demand_nodes_project_type_score", "demand_nodes", ["project_id", "type", "score"]
    )
    op.create_index("ix_demand_nodes_argument", "demand_nodes", ["argument_id"])
    op.create_index(
        "ix_demand_nodes_org_proj", "demand_nodes", ["organization_id", "project_id"]
    )

    # ── 6. Create content_cards table ───────────────────────────
    op.create_table(
        "content_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("argument_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "market",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='{"lang":"en","country":"US"}',
        ),
        sa.Column("variant_of", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("primary_demand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("primary_prompt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "secondary_demand_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("state", sa.String(16), nullable=False, server_default="backlog"),
        sa.Column("owner", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("due", sa.Date(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(500), nullable=False, server_default=""),
        sa.Column("slug", sa.String(200), nullable=False, server_default=""),
        sa.Column("outline", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("draft", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bundle_ref", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("qa_report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("cms_id", sa.String(255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "stale_claims",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("word_budget", sa.Integer(), nullable=True),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_cards_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["argument_id"],
            ["arguments.id"],
            name="fk_content_cards_argument_id_arguments",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["variant_of"],
            ["content_cards.id"],
            name="fk_content_cards_variant_of_content_cards",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["primary_demand_id"],
            ["demand_nodes.id"],
            name="fk_content_cards_primary_demand_id_demand_nodes",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["primary_prompt_id"],
            ["demand_nodes.id"],
            name="fk_content_cards_primary_prompt_id_demand_nodes",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner"],
            ["users.id"],
            name="fk_content_cards_owner_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "kind IN ('pillar', 'cluster', 'compare', 'refresh')",
            name="ck_content_cards_kind_allowed",
        ),
        sa.CheckConstraint(
            "state IN ('backlog', 'planned', 'bundled', 'outlined', 'drafting', "
            "'qa_failed', 'qa_passed', 'approved', 'live')",
            name="ck_content_cards_state_allowed",
        ),
        sa.CheckConstraint(
            "origin IN ('plan', 'import', 'insight', 'manual')",
            name="ck_content_cards_origin_allowed",
        ),
    )
    op.create_index(
        "ix_content_cards_project_state", "content_cards", ["project_id", "state"]
    )
    op.create_index(
        "ix_content_cards_project_kind", "content_cards", ["project_id", "kind"]
    )
    op.create_index("ix_content_cards_variant_of", "content_cards", ["variant_of"])
    op.create_index(
        "ix_content_cards_primary_demand", "content_cards", ["primary_demand_id"]
    )
    op.create_index(
        "uq_content_cards_project_slug",
        "content_cards",
        ["project_id", "slug"],
        unique=True,
        postgresql_where=sa.text("slug != ''"),
    )
    op.create_index(
        "ix_content_cards_org_proj", "content_cards", ["organization_id", "project_id"]
    )

    # ── 7. Create job_runs table ────────────────────────────────
    op.create_table(
        "job_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("triggered_by", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("input_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_job_runs_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_job_runs_status_allowed",
        ),
    )
    op.create_index(
        "ix_job_runs_project_type_created",
        "job_runs",
        ["project_id", "job_type", "created_at"],
    )
    op.create_index("ix_job_runs_project_status", "job_runs", ["project_id", "status"])
    op.create_index("ix_job_runs_entity", "job_runs", ["entity_type", "entity_id"])
    op.create_index(
        "ix_job_runs_org_proj", "job_runs", ["organization_id", "project_id"]
    )

    # ── 8. Enable RLS on all new V3 tables ──────────────────────
    for table in _PROJECT_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table}_tenant_all ON {table}
            USING (app_has_project_access(organization_id, project_id))
            WITH CHECK (app_has_project_access(organization_id, project_id))"""
        )

    # ── 9. Grant to application role ────────────────────────────
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'seo_content_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON
              canvases, arguments, claims, demand_nodes, content_cards, job_runs
            TO seo_content_app;
          END IF;
        END $$
        """
    )


def downgrade() -> None:
    # ── Drop RLS policies ────────────────────────────────────────
    for table in reversed(_PROJECT_SCOPED_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_all ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # ── Drop tables in reverse dependency order ──────────────────
    op.drop_table("job_runs")
    op.drop_table("content_cards")
    op.drop_table("demand_nodes")
    op.drop_table("claims")
    op.drop_table("arguments")
    op.drop_table("canvases")

    # ── Remove workspace_config column ───────────────────────────
    op.drop_column("projects", "workspace_config")
