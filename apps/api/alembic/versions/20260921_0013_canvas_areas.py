"""Add Canvas-scoped product-tree areas."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260921_0013"
down_revision: str | Sequence[str] | None = "20260921_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canvas_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("default_argument_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_areas_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["canvas_id"], ["canvases.id"], name="fk_areas_canvas_id_canvases", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["areas.id"], name="fk_areas_parent_id_areas", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["default_argument_id"],
            ["arguments.id"],
            name="fk_areas_default_argument_id_arguments",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_areas_org_proj", "areas", ["organization_id", "project_id"])
    op.create_index("ix_areas_canvas", "areas", ["canvas_id"])
    op.create_index("ix_areas_parent", "areas", ["parent_id"])
    op.create_foreign_key(
        "fk_demand_nodes_area_id_areas",
        "demand_nodes",
        "areas",
        ["area_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("ALTER TABLE areas ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE areas FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY areas_tenant_all ON areas
        USING (app_has_project_access(organization_id, project_id))
        WITH CHECK (app_has_project_access(organization_id, project_id))"""
    )
    op.execute(
        """DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'seo_content_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON areas TO seo_content_app;
          END IF;
        END $$"""
    )


def downgrade() -> None:
    op.drop_constraint("fk_demand_nodes_area_id_areas", "demand_nodes", type_="foreignkey")
    op.execute("DROP POLICY IF EXISTS areas_tenant_all ON areas")
    op.execute("ALTER TABLE areas DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_areas_parent", table_name="areas")
    op.drop_index("ix_areas_canvas", table_name="areas")
    op.drop_index("ix_areas_org_proj", table_name="areas")
    op.drop_table("areas")
