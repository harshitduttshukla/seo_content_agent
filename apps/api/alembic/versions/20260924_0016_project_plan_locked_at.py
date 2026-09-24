"""Add projects.plan_locked_at: when the Content Hub plan was first locked (V3 §5.1).

Operational state, not configuration, so it lives in its own nullable column
rather than in workspace_config. NULL means the plan has not been locked.
Additive only; existing rows keep every value and read as unlocked.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0016"
down_revision: str | Sequence[str] | None = "20260923_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("plan_locked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "plan_locked_at")
