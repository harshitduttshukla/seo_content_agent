"""Allow an authenticated transaction to bootstrap an organization and admin.

Revision ID: 20260910_0007
Revises: 20260901_0006
Create Date: 2026-09-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260910_0007"
down_revision: str | None = "20260901_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION app_can_bootstrap_organization(target_organization_id uuid)
        RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT
            public.app_current_user_id() IS NOT NULL
            AND target_organization_id =
              nullif(current_setting('app.bootstrap_organization_id', true), '')::uuid
            AND NOT EXISTS (
              SELECT 1
              FROM public.organization_members
              WHERE organization_id = target_organization_id
            )
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app_can_bootstrap_organization(uuid) FROM PUBLIC")
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'seo_content_app') THEN
            GRANT EXECUTE ON FUNCTION app_can_bootstrap_organization(uuid)
              TO seo_content_app;
          END IF;
        END $$
        """
    )

    op.execute("DROP POLICY organizations_select ON organizations")
    op.execute("DROP POLICY organizations_insert ON organizations")
    op.execute("DROP POLICY organization_members_select ON organization_members")
    op.execute(
        """
        CREATE POLICY organizations_select ON organizations
        FOR SELECT USING (
          app_is_org_member(id) OR app_can_bootstrap_organization(id)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY organizations_insert ON organizations
        FOR INSERT WITH CHECK (app_can_bootstrap_organization(id))
        """
    )
    op.execute(
        """
        CREATE POLICY organization_members_select ON organization_members
        FOR SELECT USING (
          app_is_org_member(organization_id)
          OR (
            user_id = app_current_user_id()
            AND app_can_bootstrap_organization(organization_id)
          )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY organization_members_select ON organization_members")
    op.execute("DROP POLICY organizations_insert ON organizations")
    op.execute("DROP POLICY organizations_select ON organizations")
    op.execute(
        """
        CREATE POLICY organizations_select ON organizations
        FOR SELECT USING (app_is_org_member(id))
        """
    )
    op.execute(
        """
        CREATE POLICY organizations_insert ON organizations
        FOR INSERT WITH CHECK (true)
        """
    )
    op.execute(
        """
        CREATE POLICY organization_members_select ON organization_members
        FOR SELECT USING (app_is_org_member(organization_id))
        """
    )
    op.execute("DROP FUNCTION app_can_bootstrap_organization(uuid)")
