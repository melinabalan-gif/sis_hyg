"""Record who administered each functional assignment.

Revision ID: 20260906_0010
Revises: 20260906_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260906_0010"
down_revision: str | None = "20260906_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "worksite_functional_assignments",
        sa.Column("assigned_by_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("worksite_functional_assignments", "assigned_by_actor_id")
