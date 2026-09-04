"""Add append-only synthetic document metadata versions.

Revision ID: 20260903_0005
Revises: 20260903_0004
Create Date: 2026-09-03 02:00:00

Only metadata is versioned in this revision. File assets and binary upload
flows remain outside the pilot scope.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260903_0005"
down_revision: str | None = "20260903_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_SETTING = "NULLIF(current_setting('app.current_organization_id', true), '')::uuid"
_LEGACY_ACTOR_ID = "00000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_versions"),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_document_versions_organization_id_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "document_id",
            "version_number",
            name="uq_document_versions_org_document_version",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_document_versions_organization_id_organizations",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name="fk_document_versions_org_document_documents",
        ),
        sa.CheckConstraint(
            "review_status IN ('PENDIENTE', 'APROBADO', 'RECHAZADO')",
            name="valid_review_status",
        ),
        sa.CheckConstraint(
            "expires_on IS NULL OR valid_from IS NULL OR expires_on >= valid_from",
            name="valid_date_range",
        ),
        sa.CheckConstraint("version_number > 0", name="positive_version_number"),
        sa.CheckConstraint("btrim(title) <> ''", name="title_not_blank"),
        sa.CheckConstraint("btrim(document_type) <> ''", name="document_type_not_blank"),
    )
    op.create_index(
        "ix_document_versions_org_document_version",
        "document_versions",
        ["organization_id", "document_id", "version_number"],
        unique=False,
    )

    # Documents that predate this revision receive a synthetic v1 snapshot.
    op.execute(
        sa.text(
            """
            INSERT INTO document_versions
                (
                    id, organization_id, document_id, version_number, title,
                    document_type, review_status, valid_from, expires_on, notes,
                    actor_id, created_at
                )
            SELECT
                d.id, d.organization_id, d.id, 1, d.title,
                d.document_type, d.review_status, d.valid_from, d.expires_on, d.notes,
                CAST(:actor_id AS uuid), d.created_at
            FROM documents AS d
            WHERE NOT EXISTS (
                SELECT 1
                FROM document_versions AS existing
                WHERE existing.organization_id = d.organization_id
                  AND existing.document_id = d.id
                  AND existing.version_number = 1
            )
            """
        ).bindparams(actor_id=_LEGACY_ACTOR_ID)
    )

    op.execute("ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE document_versions FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY document_versions_tenant_isolation ON document_versions
        AS PERMISSIVE FOR ALL
        USING (organization_id = {_TENANT_SETTING})
        WITH CHECK (organization_id = {_TENANT_SETTING})
        """
    )
    op.execute("REVOKE ALL PRIVILEGES ON TABLE document_versions FROM PUBLIC")
    op.execute(
        """
        DO $migration$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hys_app') THEN
                RAISE EXCEPTION 'required runtime role hys_app does not exist';
            END IF;
            GRANT SELECT, INSERT ON TABLE document_versions TO hys_app;
        END
        $migration$
        """
    )


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON TABLE document_versions FROM hys_app")
    op.execute("DROP POLICY IF EXISTS document_versions_tenant_isolation ON document_versions")
    op.drop_index(
        "ix_document_versions_org_document_version",
        table_name="document_versions",
    )
    op.drop_table("document_versions")
