"""GSC tenant integrity: same-tenant composite foreign keys and FORCEd RLS.

Before this, gsc_properties referenced websites and gsc_connections by id alone and
gsc_search_analytics referenced gsc_properties by id alone, so the database accepted
a row of one organization/project pointing at another's website, connection or
property. Each reference now carries (organization_id, project_id): the referenced
row must belong to the same tenant. Analytics rows also carry website_id into the
reference, so a row's website is always its property's website.

RLS on the three GSC tables is FORCEd so a table owner is subject to the policy too.

No data is changed. If existing rows already point across tenants, the upgrade stops
and reports the counts instead of deleting or reassigning anything.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260927_0020"
down_revision: str | Sequence[str] | None = "20260926_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("gsc_connections", "gsc_properties", "gsc_search_analytics")

PRECHECK = """
DO $$
DECLARE
  property_website integer;
  property_connection integer;
  analytics_property integer;
BEGIN
  SELECT count(*) INTO property_website FROM gsc_properties p JOIN websites w ON w.id = p.website_id
   WHERE (w.organization_id, w.project_id) IS DISTINCT FROM (p.organization_id, p.project_id);
  SELECT count(*) INTO property_connection
    FROM gsc_properties p JOIN gsc_connections c ON c.id = p.connection_id
   WHERE (c.organization_id, c.project_id) IS DISTINCT FROM (p.organization_id, p.project_id);
  SELECT count(*) INTO analytics_property
    FROM gsc_search_analytics a JOIN gsc_properties p ON p.id = a.property_id
   WHERE (p.organization_id, p.project_id, p.website_id)
         IS DISTINCT FROM (a.organization_id, a.project_id, a.website_id);
  IF property_website + property_connection + analytics_property > 0 THEN
    RAISE EXCEPTION 'GSC rows reference another tenant: % gsc_properties→websites, '
      '% gsc_properties→gsc_connections, % gsc_search_analytics→gsc_properties. '
      'Reconcile them before upgrading; nothing was changed.',
      property_website, property_connection, analytics_property;
  END IF;
END $$
"""


def upgrade() -> None:
    op.execute(PRECHECK)

    # Referenced keys that carry the tenant.
    op.create_unique_constraint(
        "uq_websites_org_proj_id", "websites", ["organization_id", "project_id", "id"]
    )
    op.create_unique_constraint(
        "uq_gsc_connections_org_proj_id",
        "gsc_connections",
        ["organization_id", "project_id", "id"],
    )
    op.create_unique_constraint(
        "uq_gsc_properties_org_proj_website_id",
        "gsc_properties",
        ["organization_id", "project_id", "website_id", "id"],
    )

    op.drop_constraint("fk_gsc_properties_website", "gsc_properties", type_="foreignkey")
    op.drop_constraint("fk_gsc_properties_connection", "gsc_properties", type_="foreignkey")
    op.create_foreign_key(
        "fk_gsc_properties_org_proj_website",
        "gsc_properties",
        "websites",
        ["organization_id", "project_id", "website_id"],
        ["organization_id", "project_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_gsc_properties_org_proj_connection",
        "gsc_properties",
        "gsc_connections",
        ["organization_id", "project_id", "connection_id"],
        ["organization_id", "project_id", "id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "fk_gsc_search_analytics_property", "gsc_search_analytics", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_gsc_search_analytics_org_proj_website_property",
        "gsc_search_analytics",
        "gsc_properties",
        ["organization_id", "project_id", "website_id", "property_id"],
        ["organization_id", "project_id", "website_id", "id"],
        ondelete="CASCADE",
    )

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")

    op.drop_constraint(
        "fk_gsc_search_analytics_org_proj_website_property",
        "gsc_search_analytics",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_gsc_search_analytics_property",
        "gsc_search_analytics",
        "gsc_properties",
        ["property_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "fk_gsc_properties_org_proj_connection", "gsc_properties", type_="foreignkey"
    )
    op.drop_constraint("fk_gsc_properties_org_proj_website", "gsc_properties", type_="foreignkey")
    op.create_foreign_key(
        "fk_gsc_properties_connection",
        "gsc_properties",
        "gsc_connections",
        ["connection_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_gsc_properties_website",
        "gsc_properties",
        "websites",
        ["website_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("uq_gsc_properties_org_proj_website_id", "gsc_properties", type_="unique")
    op.drop_constraint("uq_gsc_connections_org_proj_id", "gsc_connections", type_="unique")
    op.drop_constraint("uq_websites_org_proj_id", "websites", type_="unique")
