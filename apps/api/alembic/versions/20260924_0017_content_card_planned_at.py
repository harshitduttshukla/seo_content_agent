"""Add content_cards.planned_at: when a card most recently entered Planned (V3 §5.1).

Lets the board mark a card "new" when it entered Planned after the plan was
locked, which created_at cannot express for backlog → planned moves.
Additive only; existing cards keep NULL — no historical time is fabricated.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0017"
down_revision: str | Sequence[str] | None = "20260924_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "content_cards",
        sa.Column("planned_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("content_cards", "planned_at")
