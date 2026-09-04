"""Add worksite jurisdiction and tenant-scoped temporal stages.

Revision ID: 20260903_0004
Revises: 20260903_0003
Create Date: 2026-09-03 01:00:00

The jurisdiction default preserves existing worksites while the API requires
the field for new worksite creation. Stages are append-only in this slice and
may overlap; only each individual interval is validated.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260903_0004"
down_revision: str | None = "20260903_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_SETTING = "NULLIF(current_setting('app.current_organization_id', true), '')::uuid"


def upgrade() -> None:
    op.add_column(
        "worksites",
        sa.Column(
            "jurisdiction",
            sa.String(length=200),
            server_default=sa.text("'SIN_ESPECIFICAR'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "jurisdiction_not_blank",
        "worksites",
        "btrim(jurisdiction) <> ''",
    )

    op.create_table(
        "worksite_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("worksite_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("sector", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_worksite_stages"),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_worksite_stages_organization_id_id",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_worksite_stages_organization_id_organizations",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "worksite_id"],
            ["worksites.organization_id", "worksites.id"],
            name="fk_worksite_stages_org_worksite_worksites",
        ),
        sa.CheckConstraint(
            "ended_on IS NULL OR ended_on > started_on",
            name="valid_date_range",
        ),
        sa.CheckConstraint("btrim(code) <> ''", name="code_not_blank"),
        sa.CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
        sa.CheckConstraint(
            "sector IS NULL OR btrim(sector) <> ''",
            name="sector_not_blank",
        ),
        sa.CheckConstraint(
            "notes IS NULL OR btrim(notes) <> ''",
            name="notes_not_blank",
        ),
    )
    op.create_index(
        "ix_worksite_stages_org_worksite_started",
        "worksite_stages",
        ["organization_id", "worksite_id", "started_on", "ended_on"],
        unique=False,
    )

    op.execute("ALTER TABLE worksite_stages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE worksite_stages FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY worksite_stages_tenant_isolation ON worksite_stages
        AS PERMISSIVE FOR ALL
        USING (organization_id = {_TENANT_SETTING})
        WITH CHECK (organization_id = {_TENANT_SETTING})
        """
    )
    op.execute("REVOKE ALL PRIVILEGES ON TABLE worksite_stages FROM PUBLIC")
    op.execute(
        """
        DO $migration$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hys_app') THEN
                RAISE EXCEPTION 'required runtime role hys_app does not exist';
            END IF;
            GRANT SELECT, INSERT ON TABLE worksite_stages TO hys_app;
        END
        $migration$
        """
    )


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON TABLE worksite_stages FROM hys_app")
    op.execute("DROP POLICY IF EXISTS worksite_stages_tenant_isolation ON worksite_stages")
    op.drop_index("ix_worksite_stages_org_worksite_started", table_name="worksite_stages")
    op.drop_table("worksite_stages")
    op.drop_constraint("jurisdiction_not_blank", "worksites", type_="check")
    op.drop_column("worksites", "jurisdiction")
