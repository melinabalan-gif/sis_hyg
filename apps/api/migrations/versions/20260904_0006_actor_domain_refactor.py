"""Add explicit professions, worksite functions, contractor hierarchy and audit context.

Revision ID: 20260904_0006
Revises: 20260903_0005

The actor identifiers remain the pilot adapter's synthetic UUIDs.  This revision
does not create an authentication table and leaves legacy audit context nullable
when it cannot be determined safely.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260904_0006"
down_revision: str | None = "20260903_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_SETTING = "NULLIF(current_setting('app.current_organization_id', true), '')::uuid"
_PILOT_TENANT = "00000000-0000-4000-8000-000000000001"


def _configure_assignment_security() -> None:
    table = "worksite_functional_assignments"
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON {table}
        AS PERMISSIVE FOR ALL
        USING (organization_id = {_TENANT_SETTING})
        WITH CHECK (organization_id = {_TENANT_SETTING})
        """
    )
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE {table} FROM PUBLIC")
    op.execute(
        """
        DO $migration$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hys_app') THEN
                RAISE EXCEPTION 'required runtime role hys_app does not exist';
            END IF;
            GRANT SELECT, INSERT, UPDATE ON TABLE worksite_functional_assignments TO hys_app;
        END
        $migration$
        """
    )


def upgrade() -> None:
    # The legacy schema allowed duplicate company/worksite rows.  Refuse that
    # ambiguous backfill before changing the schema rather than deleting history.
    op.execute(
        sa.text(
            """
            DO $migration$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM worksite_contractors
                    GROUP BY organization_id, worksite_id, contractor_id
                    HAVING count(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'cannot backfill duplicate worksite contractor participation rows';
                END IF;
            END
            $migration$
            """
        )
    )
    op.add_column(
        "people",
        sa.Column(
            "profession_code", sa.String(length=32), server_default=sa.text("'OTRA'"), nullable=True
        ),
    )
    op.execute("UPDATE people SET profession_code = 'OTRA' WHERE profession_code IS NULL")
    op.alter_column("people", "profession_code", nullable=False, server_default=sa.text("'OTRA'"))
    op.create_check_constraint(
        "valid_profession_code",
        "people",
        "profession_code IN ('LICENCIADO_HYS', 'TECNICO_HYS', 'CONTRATISTA', 'OTRA')",
    )

    op.add_column(
        "worksite_contractors",
        sa.Column(
            "participation_type",
            sa.String(length=32),
            server_default=sa.text("'CONTRACTOR'"),
            nullable=True,
        ),
    )
    op.add_column(
        "worksite_contractors",
        sa.Column("parent_contracting_company_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Existing single-company worksite data is treated as the principal.  If a
    # database already has several participants, keep one deterministic
    # principal and attach the rest to it rather than inventing actors.
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY organization_id, worksite_id
                           ORDER BY started_on, created_at, id
                       ) AS row_number
                FROM worksite_contractors
            )
            UPDATE worksite_contractors AS assignment
            SET participation_type = CASE WHEN ranked.row_number = 1 THEN 'PRINCIPAL' ELSE 'CONTRACTOR' END
            FROM ranked
            WHERE assignment.id = ranked.id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE worksite_contractors AS child
            SET parent_contracting_company_id = principal.contractor_id
            FROM worksite_contractors AS principal
            WHERE child.organization_id = principal.organization_id
              AND child.worksite_id = principal.worksite_id
              AND principal.participation_type = 'PRINCIPAL'
              AND child.participation_type <> 'PRINCIPAL'
            """
        )
    )
    op.alter_column("worksite_contractors", "participation_type", nullable=False)
    op.create_unique_constraint(
        "uq_worksite_contractors_org_worksite_contractor",
        "worksite_contractors",
        ["organization_id", "worksite_id", "contractor_id"],
    )
    op.create_foreign_key(
        "fk_worksite_contractors_org_worksite_parent",
        "worksite_contractors",
        "worksite_contractors",
        ["organization_id", "worksite_id", "parent_contracting_company_id"],
        ["organization_id", "worksite_id", "contractor_id"],
    )
    op.create_check_constraint(
        "valid_participation_type",
        "worksite_contractors",
        "participation_type IN ('PRINCIPAL', 'CONTRACTOR', 'SUBCONTRACTOR')",
    )
    op.create_check_constraint(
        "parent_required_for_non_principal",
        "worksite_contractors",
        "(participation_type = 'PRINCIPAL' AND parent_contracting_company_id IS NULL) OR "
        "(participation_type <> 'PRINCIPAL' AND parent_contracting_company_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "parent_cannot_be_self",
        "worksite_contractors",
        "parent_contracting_company_id IS NULL OR parent_contracting_company_id <> contractor_id",
    )
    op.create_index(
        "uq_worksite_contractors_one_principal",
        "worksite_contractors",
        ["organization_id", "worksite_id"],
        unique=True,
        postgresql_where=sa.text("participation_type = 'PRINCIPAL'"),
    )

    op.create_table(
        "worksite_functional_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("worksite_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("function_code", sa.String(length=64), nullable=False),
        sa.Column("represented_contractor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "permission_scope",
            sa.String(length=32),
            server_default=sa.text("'WORKSITE'"),
            nullable=False,
        ),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_worksite_functional_assignments"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_worksite_functional_assignments_organization_id_id"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "worksite_id",
            "id",
            name="uq_worksite_functional_assignments_org_worksite_id",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_wfa_organization_id_organizations",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "worksite_id"],
            ["worksites.organization_id", "worksites.id"],
            name="fk_worksite_functional_assignments_org_worksite_worksites",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "person_id"],
            ["people.organization_id", "people.id"],
            name="fk_worksite_functional_assignments_org_person_people",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "represented_contractor_id"],
            ["contractors.organization_id", "contractors.id"],
            name="fk_worksite_functional_assignments_org_contractor_contractors",
        ),
        sa.CheckConstraint(
            "function_code IN ('RESPONSABLE_HYS_PROYECTO', 'AUDITOR_DELEGADO_PROYECTO', "
            "'RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL', 'TECNICO_HYS_CONTRATISTA_PRINCIPAL')",
            name="valid_function_code",
        ),
        sa.CheckConstraint(
            "permission_scope IN ('WORKSITE', 'ORGANIZATION')", name="valid_permission_scope"
        ),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_date_range"),
    )
    op.create_index(
        "ix_worksite_functional_assignments_org_worksite_actor_active",
        "worksite_functional_assignments",
        ["organization_id", "worksite_id", "actor_id", "valid_to"],
    )
    op.create_index(
        "ix_worksite_functional_assignments_org_worksite_function",
        "worksite_functional_assignments",
        ["organization_id", "worksite_id", "function_code"],
    )
    _configure_assignment_security()

    op.add_column(
        "audits", sa.Column("auditor_actor_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "audits", sa.Column("auditor_assignment_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "audits",
        sa.Column(
            "associated_professional_person_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.add_column("audits", sa.Column("audit_date", sa.Date(), nullable=True))
    op.create_foreign_key(
        "fk_audits_org_worksite_auditor_assignment",
        "audits",
        "worksite_functional_assignments",
        ["organization_id", "worksite_id", "auditor_assignment_id"],
        ["organization_id", "worksite_id", "id"],
    )
    op.create_foreign_key(
        "fk_audits_org_professional_person_people",
        "audits",
        "people",
        ["organization_id", "associated_professional_person_id"],
        ["organization_id", "id"],
    )
    op.create_index(
        "ix_audits_org_worksite_auditor_assignment",
        "audits",
        ["organization_id", "worksite_id", "auditor_assignment_id"],
    )


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON TABLE worksite_functional_assignments FROM hys_app")
    op.execute(
        "DROP POLICY IF EXISTS worksite_functional_assignments_tenant_isolation ON worksite_functional_assignments"
    )
    op.drop_index("ix_audits_org_worksite_auditor_assignment", table_name="audits")
    op.drop_constraint("fk_audits_org_professional_person_people", "audits", type_="foreignkey")
    op.drop_constraint("fk_audits_org_worksite_auditor_assignment", "audits", type_="foreignkey")
    for column in (
        "audit_date",
        "associated_professional_person_id",
        "auditor_assignment_id",
        "auditor_actor_id",
    ):
        op.drop_column("audits", column)

    op.drop_index(
        "ix_worksite_functional_assignments_org_worksite_function",
        table_name="worksite_functional_assignments",
    )
    op.drop_index(
        "ix_worksite_functional_assignments_org_worksite_actor_active",
        table_name="worksite_functional_assignments",
    )
    op.drop_table("worksite_functional_assignments")

    op.drop_index("uq_worksite_contractors_one_principal", table_name="worksite_contractors")
    op.drop_constraint("parent_cannot_be_self", "worksite_contractors", type_="check")
    op.drop_constraint("parent_required_for_non_principal", "worksite_contractors", type_="check")
    op.drop_constraint("valid_participation_type", "worksite_contractors", type_="check")
    op.drop_constraint(
        "fk_worksite_contractors_org_worksite_parent", "worksite_contractors", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_worksite_contractors_org_worksite_contractor", "worksite_contractors", type_="unique"
    )
    op.drop_column("worksite_contractors", "parent_contracting_company_id")
    op.drop_column("worksite_contractors", "participation_type")

    op.drop_constraint("valid_profession_code", "people", type_="check")
    op.drop_column("people", "profession_code")
