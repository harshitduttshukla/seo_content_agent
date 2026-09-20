"""Add base_version to ai_edit_proposals for optimistic concurrency.

Revision ID: 20260916_0010
Revises: 20260916_0009
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0010"
down_revision: str | None = "20260916_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_edit_proposals",
        sa.Column("base_version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("ai_edit_proposals", "base_version")
