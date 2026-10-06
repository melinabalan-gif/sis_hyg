"""Add address to worksites.

Revision ID: 20261001_0011
Revises: 20260906_0010
"""

import sqlalchemy as sa

from alembic import op


revision: str = "20261001_0011"
down_revision: str | None = "20260906_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "worksites",
        sa.Column("address", sa.String(length=240), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("worksites", "address")
