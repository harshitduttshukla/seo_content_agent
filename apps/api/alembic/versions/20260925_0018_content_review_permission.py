"""Add the content.review permission for V3 gate decisions (G1 outline review).

Gates are a human decision (handoff §5.2-5.4) that writers must not take on
their own work, and content.write does not separate them. Granted to admin,
seo_manager, content_manager and editor; writer and viewer do not get it.
Data-only: one permission row and its role grants.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260925_0018"
down_revision: str | Sequence[str] | None = "20260924_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSION_ID = "00000000-0000-0000-0000-000000000124"
PERMISSION_CODE = "content.review"
GRANTED_ROLE_IDS = (
    "00000000-0000-0000-0000-000000000001",  # admin
    "00000000-0000-0000-0000-000000000002",  # seo_manager
    "00000000-0000-0000-0000-000000000003",  # content_manager
    "00000000-0000-0000-0000-000000000005",  # editor
)


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO permissions (id, code, description) "
            "VALUES (CAST(:id AS uuid), :code, :description)"
        ).bindparams(
            id=PERMISSION_ID, code=PERMISSION_CODE, description=f"Allows {PERMISSION_CODE}"
        )
    )
    for role_id in GRANTED_ROLE_IDS:
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "VALUES (CAST(:role_id AS uuid), CAST(:permission_id AS uuid))"
            ).bindparams(role_id=role_id, permission_id=PERMISSION_ID)
        )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_id = CAST(:id AS uuid)").bindparams(
            id=PERMISSION_ID
        )
    )
    op.execute(
        sa.text("DELETE FROM permissions WHERE id = CAST(:id AS uuid)").bindparams(id=PERMISSION_ID)
    )
