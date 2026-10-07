"""Bind new reviews to immutable document versions without inventing legacy history."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261006_0012"
down_revision: str | None = "20261001_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_document_versions_org_document_id",
        "document_versions",
        ["organization_id", "document_id", "id"],
    )
    op.add_column(
        "document_reviews",
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_reviews_org_document_version",
        "document_reviews",
        "document_versions",
        ["organization_id", "document_id", "document_version_id"],
        ["organization_id", "document_id", "id"],
    )
    # NOT VALID preserves unknown legacy links while checking every new insert.
    op.create_check_constraint(
        op.f("ck_document_reviews_version_required"),
        "document_reviews",
        "document_version_id IS NOT NULL",
        postgresql_not_valid=True,
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_document_reviews_version_required"), "document_reviews", type_="check"
    )
    op.drop_constraint(
        "fk_document_reviews_org_document_version", "document_reviews", type_="foreignkey"
    )
    op.drop_column("document_reviews", "document_version_id")
    op.drop_constraint("uq_document_versions_org_document_id", "document_versions", type_="unique")
