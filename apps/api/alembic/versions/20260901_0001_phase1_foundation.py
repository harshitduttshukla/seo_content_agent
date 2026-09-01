"""Create the Phase 1 SaaS foundation.

Revision ID: 20260901_0001
Revises:
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260901_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_IDS = {
    "admin": "00000000-0000-0000-0000-000000000001",
    "seo_manager": "00000000-0000-0000-0000-000000000002",
    "content_manager": "00000000-0000-0000-0000-000000000003",
    "writer": "00000000-0000-0000-0000-000000000004",
    "editor": "00000000-0000-0000-0000-000000000005",
    "viewer": "00000000-0000-0000-0000-000000000006",
}

PERMISSION_CODES = [
    "organization.read",
    "organization.update",
    "members.read",
    "members.manage",
    "project.read",
    "project.create",
    "project.update",
    "project.delete",
    "website.read",
    "website.create",
    "website.update",
    "website.delete",
    "strategy.read",
    "strategy.write",
    "keyword.read",
    "keyword.write",
    "content.read",
    "content.write",
    "seo.read",
    "seo.write",
    "ai.use",
    "ai.write",
    "publish.execute",
]
PERMISSION_IDS = {
    code: f"00000000-0000-0000-0000-{index:012d}"
    for index, code in enumerate(PERMISSION_CODES, start=101)
}

ROLE_PERMISSIONS = {
    "admin": set(PERMISSION_CODES),
    "seo_manager": {
        "organization.read",
        "members.read",
        "project.read",
        "project.create",
        "project.update",
        "website.read",
        "website.create",
        "website.update",
        "strategy.read",
        "strategy.write",
        "keyword.read",
        "keyword.write",
        "content.read",
        "content.write",
        "seo.read",
        "seo.write",
        "ai.use",
        "ai.write",
    },
    "content_manager": {
        "organization.read",
        "members.read",
        "project.read",
        "project.update",
        "website.read",
        "strategy.read",
        "keyword.read",
        "content.read",
        "content.write",
        "seo.read",
        "ai.use",
        "ai.write",
    },
    "writer": {
        "organization.read",
        "project.read",
        "website.read",
        "strategy.read",
        "keyword.read",
        "content.read",
        "content.write",
        "seo.read",
        "ai.use",
    },
    "editor": {
        "organization.read",
        "project.read",
        "website.read",
        "strategy.read",
        "keyword.read",
        "content.read",
        "content.write",
        "seo.read",
        "ai.use",
        "publish.execute",
    },
    "viewer": {
        "organization.read",
        "project.read",
        "website.read",
        "strategy.read",
        "keyword.read",
        "content.read",
        "seo.read",
    },
}


def uuid_column(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    op.create_table(
        "users",
        uuid_column("id"),
        sa.Column("identity_issuer", sa.String(500), nullable=False),
        sa.Column("identity_subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("normalized_email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint("status IN ('active', 'suspended')", name="ck_users_status_allowed"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint(
            "identity_issuer", "identity_subject", name="uq_users_identity_issuer_identity_subject"
        ),
    )
    op.create_index("ix_users_normalized_email", "users", ["normalized_email"])

    op.create_table(
        "roles",
        uuid_column("id"),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("scope", sa.String(32), server_default="both", nullable=False),
        sa.Column("description", sa.String(500), server_default="", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "scope IN ('organization', 'project', 'both')", name="ck_roles_scope_allowed"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_table(
        "permissions",
        uuid_column("id"),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), server_default="", nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_permissions"),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_table(
        "role_permissions",
        uuid_column("role_id"),
        uuid_column("permission_id"),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_role_permissions_role_id_roles", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name="fk_role_permissions_permission_id_permissions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permissions"),
    )

    op.create_table(
        "organizations",
        uuid_column("id"),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column(
            "settings", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'archived')",
            name="ck_organizations_status_allowed",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
    )
    op.create_index(
        "uq_organizations_active_slug",
        "organizations",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.create_index("ix_organizations_status_created", "organizations", ["status", "created_at"])

    op.create_table(
        "organization_members",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("user_id"),
        uuid_column("role_id"),
        uuid_column("invited_by_id", nullable=True),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('active', 'suspended')", name="ck_organization_members_status_allowed"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_members_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_organization_members_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_organization_members_role_id_roles",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_id"],
            ["users.id"],
            name="fk_organization_members_invited_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_members"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_members_org_user_composite"),
    )
    op.create_index(
        "ix_organization_members_user_status", "organization_members", ["user_id", "status"]
    )
    op.create_index(
        "ix_organization_members_org_status",
        "organization_members",
        ["organization_id", "status"],
    )

    op.create_table(
        "projects",
        uuid_column("id"),
        uuid_column("organization_id"),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("description", sa.String(2000), server_default="", nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("default_locale", sa.String(20), server_default="en", nullable=False),
        sa.Column("default_country", sa.String(2)),
        sa.Column(
            "settings", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_projects_status_allowed"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_projects_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("organization_id", "id", name="uq_projects_organization_id_id"),
    )
    op.create_index(
        "uq_projects_active_org_slug",
        "projects",
        ["organization_id", "slug"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.create_index(
        "ix_projects_org_status_created", "projects", ["organization_id", "status", "created_at"]
    )

    op.create_table(
        "project_members",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("user_id"),
        uuid_column("role_id"),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_project_members_organization_id_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["organization_members.organization_id", "organization_members.user_id"],
            name="fk_project_members_organization_id_user_id_organization_members",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_project_members_role_id_roles", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_members"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_members_project_id_user_id"),
    )
    op.create_index("ix_project_members_user_project", "project_members", ["user_id", "project_id"])
    op.create_index(
        "ix_project_members_org_project", "project_members", ["organization_id", "project_id"]
    )

    op.create_table(
        "websites",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("base_url", sa.String(2048), nullable=False),
        sa.Column("normalized_host", sa.String(253), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("locale", sa.String(20), server_default="en", nullable=False),
        sa.Column("country", sa.String(2)),
        sa.Column(
            "verification_status", sa.String(32), server_default="unverified", nullable=False
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column(
            "settings", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'archived')", name="ck_websites_status_allowed"
        ),
        sa.CheckConstraint(
            "verification_status IN ('unverified', 'verified', 'failed')",
            name="ck_websites_verification_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_websites_organization_id_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_websites"),
    )
    op.create_index(
        "uq_websites_active_project_host_locale",
        "websites",
        ["project_id", "normalized_host", "locale"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.create_index(
        "ix_websites_org_project_status", "websites", ["organization_id", "project_id", "status"]
    )

    op.create_table(
        "audit_logs",
        uuid_column("id"),
        uuid_column("organization_id", nullable=True),
        uuid_column("project_id", nullable=True),
        uuid_column("actor_user_id", nullable=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        uuid_column("resource_id", nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_audit_logs_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_audit_logs_organization_id_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_logs_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_org_occurred", "audit_logs", ["organization_id", "occurred_at"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("ix_audit_logs_actor_occurred", "audit_logs", ["actor_user_id", "occurred_at"])

    op.create_table(
        "idempotency_records",
        uuid_column("id"),
        uuid_column("organization_id", nullable=True),
        uuid_column("actor_user_id"),
        sa.Column("route", sa.String(200), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_data", postgresql.JSONB()),
        sa.Column("status_code", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_idempotency_records_actor_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.UniqueConstraint(
            "actor_user_id",
            "route",
            "idempotency_key",
            name="uq_idempotency_records_actor_user_id_route_idempotency_key",
        ),
    )
    op.create_index("ix_idempotency_records_expires", "idempotency_records", ["expires_at"])

    op.create_table(
        "outbox_events",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id", nullable=True),
        sa.Column("aggregate_type", sa.String(80), nullable=False),
        uuid_column("aggregate_id"),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("event_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_outbox_events_organization_id_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_events"),
    )
    op.create_index(
        "ix_outbox_events_unpublished", "outbox_events", ["published_at", "occurred_at"]
    )

    _seed_rbac()
    _create_rls()


def _seed_rbac() -> None:
    roles = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("scope", sa.String()),
        sa.column("description", sa.String()),
    )
    permissions = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", postgresql.UUID(as_uuid=True)),
        sa.column("permission_id", postgresql.UUID(as_uuid=True)),
    )
    op.bulk_insert(
        roles,
        [
            {
                "id": role_id,
                "code": code,
                "name": code.replace("_", " ").title(),
                "scope": "both",
                "description": f"Built-in {code.replace('_', ' ')} role",
            }
            for code, role_id in ROLE_IDS.items()
        ],
    )
    op.bulk_insert(
        permissions,
        [
            {"id": permission_id, "code": code, "description": f"Allows {code}"}
            for code, permission_id in PERMISSION_IDS.items()
        ],
    )
    op.bulk_insert(
        role_permissions,
        [
            {"role_id": ROLE_IDS[role], "permission_id": PERMISSION_IDS[permission]}
            for role, role_permissions_set in ROLE_PERMISSIONS.items()
            for permission in sorted(role_permissions_set)
        ],
    )


def _create_rls() -> None:
    op.execute(
        """
        CREATE FUNCTION app_current_user_id() RETURNS uuid
        LANGUAGE sql STABLE
        AS $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app_is_org_member(target_organization_id uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM public.organization_members
            WHERE organization_id = target_organization_id
              AND user_id = public.app_current_user_id()
              AND status = 'active'
          )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app_has_project_access(target_organization_id uuid, target_project_id uuid)
        RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
        AS $$
          SELECT EXISTS (
            SELECT 1
            FROM public.organization_members om
            JOIN public.roles r ON r.id = om.role_id
            LEFT JOIN public.project_members pm
              ON pm.organization_id = om.organization_id
             AND pm.user_id = om.user_id
             AND pm.project_id = target_project_id
            WHERE om.organization_id = target_organization_id
              AND om.user_id = public.app_current_user_id()
              AND om.status = 'active'
              AND (r.code = 'admin' OR pm.id IS NOT NULL)
          )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app_can_manage_org_members(target_organization_id uuid, target_user_id uuid)
        RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
        AS $$
          SELECT public.app_is_org_member(target_organization_id)
             OR (
               target_user_id = public.app_current_user_id()
               AND NOT EXISTS (
                 SELECT 1 FROM public.organization_members
                 WHERE organization_id = target_organization_id
               )
             )
        $$
        """
    )

    for table in (
        "organizations",
        "organization_members",
        "projects",
        "project_members",
        "websites",
        "audit_logs",
        "idempotency_records",
        "outbox_events",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    op.execute(
        """CREATE POLICY organizations_select ON organizations
        FOR SELECT USING (app_is_org_member(id))"""
    )
    op.execute("CREATE POLICY organizations_insert ON organizations FOR INSERT WITH CHECK (true)")
    op.execute(
        """CREATE POLICY organizations_update ON organizations FOR UPDATE
        USING (app_is_org_member(id)) WITH CHECK (app_is_org_member(id))"""
    )
    op.execute(
        """CREATE POLICY organization_members_select ON organization_members
        FOR SELECT USING (app_is_org_member(organization_id))"""
    )
    op.execute(
        """CREATE POLICY organization_members_insert ON organization_members
        FOR INSERT WITH CHECK (app_can_manage_org_members(organization_id, user_id))"""
    )
    op.execute(
        """CREATE POLICY organization_members_update ON organization_members FOR UPDATE
        USING (app_is_org_member(organization_id))
        WITH CHECK (app_is_org_member(organization_id))"""
    )
    op.execute(
        """CREATE POLICY projects_all ON projects
        USING (app_has_project_access(organization_id, id))
        WITH CHECK (app_is_org_member(organization_id))"""
    )
    op.execute(
        """CREATE POLICY project_members_all ON project_members
        USING (app_has_project_access(organization_id, project_id))
        WITH CHECK (app_is_org_member(organization_id))"""
    )
    op.execute(
        """CREATE POLICY websites_all ON websites
        USING (app_has_project_access(organization_id, project_id))
        WITH CHECK (app_has_project_access(organization_id, project_id))"""
    )
    op.execute(
        """CREATE POLICY audit_logs_all ON audit_logs
        USING (
          (organization_id IS NULL AND actor_user_id = app_current_user_id())
          OR app_is_org_member(organization_id)
        )
        WITH CHECK (
          (organization_id IS NULL AND actor_user_id = app_current_user_id())
          OR app_is_org_member(organization_id)
        )"""
    )
    op.execute(
        """CREATE POLICY idempotency_records_all ON idempotency_records
        USING (actor_user_id = app_current_user_id())
        WITH CHECK (actor_user_id = app_current_user_id())"""
    )
    op.execute(
        """CREATE POLICY outbox_events_all ON outbox_events
        USING (app_is_org_member(organization_id))
        WITH CHECK (app_is_org_member(organization_id))"""
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'seo_content_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public
              TO seo_content_app;
            GRANT EXECUTE ON FUNCTION app_current_user_id() TO seo_content_app;
            GRANT EXECUTE ON FUNCTION app_is_org_member(uuid) TO seo_content_app;
            GRANT EXECUTE ON FUNCTION app_has_project_access(uuid, uuid) TO seo_content_app;
            GRANT EXECUTE ON FUNCTION app_can_manage_org_members(uuid, uuid)
              TO seo_content_app;
          END IF;
        END $$
        """
    )


def downgrade() -> None:
    policies = (
        ("organizations", "organizations_select"),
        ("organizations", "organizations_insert"),
        ("organizations", "organizations_update"),
        ("organization_members", "organization_members_select"),
        ("organization_members", "organization_members_insert"),
        ("organization_members", "organization_members_update"),
        ("projects", "projects_all"),
        ("project_members", "project_members_all"),
        ("websites", "websites_all"),
        ("audit_logs", "audit_logs_all"),
        ("idempotency_records", "idempotency_records_all"),
        ("outbox_events", "outbox_events_all"),
    )
    for table, policy in policies:
        op.execute(f"DROP POLICY {policy} ON {table}")
    op.execute("DROP FUNCTION app_can_manage_org_members(uuid, uuid)")
    op.execute("DROP FUNCTION app_has_project_access(uuid, uuid)")
    op.execute("DROP FUNCTION app_is_org_member(uuid)")
    op.execute("DROP FUNCTION app_current_user_id()")
    for table in (
        "outbox_events",
        "idempotency_records",
        "audit_logs",
        "websites",
        "project_members",
        "projects",
        "organization_members",
        "organizations",
    ):
        op.drop_table(table)
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
