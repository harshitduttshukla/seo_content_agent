"""Google Search Console: connections, property mappings, Search Analytics rows (Phase 6A).

Additive. All three tables are project-scoped with the same RLS policy as the V3
tables (app_has_project_access) and are granted to the application role.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260926_0019"
down_revision: str | Sequence[str] | None = "20260925_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("gsc_connections", "gsc_properties", "gsc_search_analytics")
UUID = postgresql.UUID(as_uuid=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "gsc_connections",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("google_account_email", sa.String(320)),
        sa.Column("encrypted_refresh_token", sa.Text()),
        sa.Column("scopes", sa.Text(), nullable=False, server_default=""),
        sa.Column("oauth_state_hash", sa.String(64)),
        sa.Column("oauth_state_expires_at", sa.DateTime(timezone=True)),
        sa.Column("oauth_started_by", UUID),
        sa.Column("connected_by", UUID),
        sa.Column("connected_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_gsc_connections_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("project_id", name="uq_gsc_connections_project"),
        sa.CheckConstraint(
            "status IN ('pending', 'connected', 'reauth_required', 'disconnected')",
            name="ck_gsc_connections_status_allowed",
        ),
    )
    op.create_index("ix_gsc_connections_oauth_state", "gsc_connections", ["oauth_state_hash"])

    op.create_table(
        "gsc_properties",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("website_id", UUID, nullable=False),
        sa.Column("connection_id", UUID, nullable=False),
        sa.Column("site_url", sa.String(2048), nullable=False),
        sa.Column("permission_level", sa.String(64), nullable=False, server_default=""),
        sa.Column("mapped_by", UUID),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_start", sa.Date()),
        sa.Column("last_sync_end", sa.Date()),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_gsc_properties_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["website_id"], ["websites.id"], name="fk_gsc_properties_website", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["gsc_connections.id"],
            name="fk_gsc_properties_connection",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("website_id", name="uq_gsc_properties_website"),
    )
    op.create_index(
        "ix_gsc_properties_org_proj", "gsc_properties", ["organization_id", "project_id"]
    )

    op.create_table(
        "gsc_search_analytics",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("website_id", UUID, nullable=False),
        sa.Column("property_id", UUID, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("page", sa.Text(), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("impressions", sa.Integer(), nullable=False),
        sa.Column("ctr", sa.Float(), nullable=False),
        sa.Column("position", sa.Float(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("job_run_id", UUID),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_gsc_search_analytics_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["gsc_properties.id"],
            name="fk_gsc_search_analytics_property",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "property_id", "date", "query", "page", name="uq_gsc_search_analytics_row"
        ),
        sa.CheckConstraint(
            "clicks >= 0 AND impressions >= 0", name="ck_gsc_search_analytics_counts"
        ),
    )
    op.create_index(
        "ix_gsc_search_analytics_property_date", "gsc_search_analytics", ["property_id", "date"]
    )
    op.create_index(
        "ix_gsc_search_analytics_org_proj",
        "gsc_search_analytics",
        ["organization_id", "project_id"],
    )

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table}_tenant_all ON {table}
            USING (app_has_project_access(organization_id, project_id))
            WITH CHECK (app_has_project_access(organization_id, project_id))"""
        )
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'seo_content_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON {", ".join(TABLES)} TO seo_content_app;
          END IF;
        END $$
        """
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_all ON {table}")
    op.drop_table("gsc_search_analytics")
    op.drop_table("gsc_properties")
    op.drop_table("gsc_connections")
