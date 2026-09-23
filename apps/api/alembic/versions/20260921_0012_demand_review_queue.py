"""Add raw review-queue fields to demand nodes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_0012"
down_revision: str | Sequence[str] | None = "52f2efacc24e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("demand_nodes", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column(
        "demand_nodes",
        sa.Column("competitor_names", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_demand_nodes_project_confidence", "demand_nodes", ["project_id", "confidence"])


def downgrade() -> None:
    op.drop_index("ix_demand_nodes_project_confidence", table_name="demand_nodes")
    op.drop_column("demand_nodes", "competitor_names")
    op.drop_column("demand_nodes", "confidence")
