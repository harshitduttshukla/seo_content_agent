"""Add the missing foreign key from content_cards.area_id to areas.id.

Without it a card whose area is deleted keeps a dangling area_id and vanishes
from every Strategy Map count. SET NULL matches demand_nodes.area_id (0013), so
such a card becomes unassigned and is reported as such.

Rows that already point at a missing area are nulled first; otherwise the
constraint cannot be created. That is the only data change.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260923_0015"
down_revision: str | Sequence[str] | None = "20260921_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """UPDATE content_cards SET area_id = NULL
        WHERE area_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM areas WHERE areas.id = content_cards.area_id)"""
    )
    op.create_foreign_key(
        "fk_content_cards_area_id_areas",
        "content_cards",
        "areas",
        ["area_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_content_cards_area_id_areas", "content_cards", type_="foreignkey")
