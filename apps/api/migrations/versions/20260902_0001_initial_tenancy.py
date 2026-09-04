"""Crea organizaciones y obras tenant-aware con RLS forzado.

Revision ID: 20260902_0001
Revises:
Create Date: 2026-09-02 00:00:00

Compatibilidad: primera revisión, requiere migrar antes de iniciar la API.
Rollback: reversible mientras no exista información que deba conservarse.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260902_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_SETTING = "NULLIF(current_setting('app.current_organization_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default=sa.text("'America/Argentina/Buenos_Aires'"),
            nullable=False,
        ),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    op.create_table(
        "worksites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default=sa.text("'ACTIVE'"), nullable=False
        ),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'ARCHIVED')", name=op.f("ck_worksites_valid_status")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_worksites_organization_id_organizations",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_worksites"),
        sa.UniqueConstraint("organization_id", "code", name="uq_worksites_organization_id_code"),
        sa.UniqueConstraint("organization_id", "id", name="uq_worksites_organization_id_id"),
    )
    op.create_index(
        "ix_worksites_organization_id_status",
        "worksites",
        ["organization_id", "status"],
        unique=False,
    )

    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organizations FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY organizations_tenant_isolation ON organizations
        AS PERMISSIVE FOR ALL
        USING (id = {_TENANT_SETTING})
        WITH CHECK (id = {_TENANT_SETTING})
        """
    )
    op.execute("ALTER TABLE worksites ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE worksites FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY worksites_tenant_isolation ON worksites
        AS PERMISSIVE FOR ALL
        USING (organization_id = {_TENANT_SETTING})
        WITH CHECK (organization_id = {_TENANT_SETTING})
        """
    )

    # Ninguna tabla queda accesible por privilegios implícitos. El provisionador
    # idempotente debe crear hys_app con mínimo privilegio antes de migrar.
    op.execute("REVOKE ALL PRIVILEGES ON TABLE alembic_version FROM PUBLIC")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE organizations FROM PUBLIC")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE worksites FROM PUBLIC")
    op.execute(
        """
        DO $migration$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hys_app') THEN
                RAISE EXCEPTION 'required runtime role hys_app does not exist';
            END IF;
            GRANT SELECT ON TABLE alembic_version TO hys_app;
            GRANT SELECT ON TABLE organizations TO hys_app;
            GRANT SELECT, INSERT, UPDATE ON TABLE worksites TO hys_app;
        END
        $migration$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $migration$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hys_app') THEN
                REVOKE SELECT ON TABLE alembic_version FROM hys_app;
                REVOKE SELECT ON TABLE organizations FROM hys_app;
                REVOKE SELECT, INSERT, UPDATE ON TABLE worksites FROM hys_app;
            END IF;
        END
        $migration$
        """
    )
    op.execute("DROP POLICY IF EXISTS worksites_tenant_isolation ON worksites")
    op.execute("DROP POLICY IF EXISTS organizations_tenant_isolation ON organizations")
    op.drop_index("ix_worksites_organization_id_status", table_name="worksites")
    op.drop_table("worksites")
    op.drop_table("organizations")
