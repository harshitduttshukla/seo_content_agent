"""v3_services_foundation

Revision ID: 52f2efacc24e
Revises: 20260918_0011
Create Date: 2026-09-19 23:50:56.707277
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "52f2efacc24e"
down_revision: str | Sequence[str] | None = "20260918_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Update demand_nodes status constraint
    op.execute(
        "ALTER TABLE demand_nodes DROP CONSTRAINT ck_demand_nodes_ck_demand_nodes_status_allowed"
    )
    op.execute(
        "ALTER TABLE demand_nodes ADD CONSTRAINT ck_demand_nodes_ck_demand_nodes_status_allowed "
        "CHECK (status IN ('pending', 'kept', 'discarded', 'pending_classify'))"
    )

    # 2. Unique index on content_cards url
    op.create_index(
        "uq_content_cards_project_url",
        "content_cards",
        ["project_id", "url"],
        unique=True,
        postgresql_where=sa.text("url IS NOT NULL"),
    )

    # 3. Create content_card_claims
    op.create_table(
        "content_card_claims",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_card_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_content_card_claims"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_content_card_claims_org_proj_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_card_id"],
            ["content_cards.id"],
            name="fk_content_card_claims_card_id_content_cards",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["claims.id"],
            name="fk_content_card_claims_claim_id_claims",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "uq_content_card_claims_card_claim",
        "content_card_claims",
        ["content_card_id", "claim_id"],
        unique=True,
    )
    op.create_index("ix_content_card_claims_claim_id", "content_card_claims", ["claim_id"])
    op.create_index(
        "ix_content_card_claims_org_proj", "content_card_claims", ["organization_id", "project_id"]
    )
    op.execute("ALTER TABLE content_card_claims ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE content_card_claims FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY content_card_claims_tenant_isolation ON content_card_claims
            USING (app_has_project_access(organization_id, project_id))
            WITH CHECK (app_has_project_access(organization_id, project_id))"""
    )


def downgrade() -> None:
    # 3. Drop content_card_claims
    op.execute("DROP POLICY IF EXISTS content_card_claims_tenant_isolation ON content_card_claims")
    op.drop_index("ix_content_card_claims_org_proj", table_name="content_card_claims")
    op.drop_index("ix_content_card_claims_claim_id", table_name="content_card_claims")
    op.drop_index("uq_content_card_claims_card_claim", table_name="content_card_claims")
    op.drop_table("content_card_claims")

    # 2. Drop unique index on content_cards
    op.drop_index("uq_content_cards_project_url", table_name="content_cards")

    # 1. Revert demand_nodes status constraint
    op.execute(
        "ALTER TABLE demand_nodes DROP CONSTRAINT ck_demand_nodes_ck_demand_nodes_status_allowed"
    )
    op.execute(
        "ALTER TABLE demand_nodes ADD CONSTRAINT ck_demand_nodes_ck_demand_nodes_status_allowed "
        "CHECK (status IN ('pending', 'kept', 'discarded'))"
    )
