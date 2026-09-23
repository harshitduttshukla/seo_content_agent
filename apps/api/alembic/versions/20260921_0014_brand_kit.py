"""Add tenant-scoped Brand Kit, voice corpus, and social proof records."""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260921_0014"
down_revision: str | Sequence[str] | None = "20260921_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_project_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY {table}_tenant_all ON {table}
        USING (app_has_project_access(organization_id, project_id))
        WITH CHECK (app_has_project_access(organization_id, project_id))"""
    )
    op.execute(
        f"""DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'seo_content_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO seo_content_app;
          END IF;
        END $$"""
    )


def upgrade() -> None:
    op.create_table(
        "brand_kits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("spelling", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("banned_words", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("style", sa.Text(), nullable=False, server_default=""),
        sa.Column("vocabulary", sa.Text(), nullable=False, server_default=""),
        sa.Column("tone_profile", sa.Text(), nullable=False, server_default=""),
        sa.Column("profile_provisional", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["organization_id", "project_id"], ["projects.organization_id", "projects.id"], name="fk_brand_kits_org_proj_projects", ondelete="CASCADE"),
    )
    op.create_index("uq_brand_kits_project", "brand_kits", ["project_id"], unique=True)
    op.create_index("ix_brand_kits_org_proj", "brand_kits", ["organization_id", "project_id"])
    op.create_table(
        "voice_snippets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_name", sa.String(length=300), nullable=False),
        sa.Column("captured_on", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["organization_id", "project_id"], ["projects.organization_id", "projects.id"], name="fk_voice_snippets_org_proj_projects", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"], name="fk_voice_snippets_area_id_areas", ondelete="SET NULL"),
    )
    op.create_index("ix_voice_snippets_org_proj", "voice_snippets", ["organization_id", "project_id"])
    op.create_table(
        "social_proofs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=500), nullable=False),
        sa.Column("proof_type", sa.String(length=50), nullable=False),
        sa.Column("area_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("markets", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["organization_id", "project_id"], ["projects.organization_id", "projects.id"], name="fk_social_proofs_org_proj_projects", ondelete="CASCADE"),
    )
    op.create_index("ix_social_proofs_org_proj", "social_proofs", ["organization_id", "project_id"])
    for table in ("brand_kits", "voice_snippets", "social_proofs"):
        _enable_project_rls(table)


def downgrade() -> None:
    for table in ("social_proofs", "voice_snippets", "brand_kits"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_all ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_social_proofs_org_proj", table_name="social_proofs")
    op.drop_table("social_proofs")
    op.drop_index("ix_voice_snippets_org_proj", table_name="voice_snippets")
    op.drop_table("voice_snippets")
    op.drop_index("ix_brand_kits_org_proj", table_name="brand_kits")
    op.drop_index("uq_brand_kits_project", table_name="brand_kits")
    op.drop_table("brand_kits")
