"""Close the remaining actor, responsibility, inspection and audit-integrity gaps.

Revision ID: 20260905_0008
Revises: 20260905_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260905_0008"
down_revision: str | None = "20260905_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("person_assignments", "contractor_id", nullable=True)

    op.drop_constraint(
        "valid_function_code",
        "worksite_functional_assignments",
        type_="check",
    )
    op.create_check_constraint(
        "valid_function_code",
        "worksite_functional_assignments",
        "function_code IN ("
        "'RESPONSABLE_HYS_PROYECTO', 'AUDITOR_DELEGADO_PROYECTO', "
        "'RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL', "
        "'TECNICO_HYS_CONTRATISTA_PRINCIPAL', "
        "'RESPONSABLE_HYS_CONTRATISTA', 'TECNICO_HYS_CONTRATISTA')",
    )

    op.add_column(
        "findings",
        sa.Column("responsible_contractor_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column("responsible_person_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_findings_org_responsible_contractor_contractors",
        "findings",
        "contractors",
        ["organization_id", "responsible_contractor_id"],
        ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_findings_org_responsible_person_people",
        "findings",
        "people",
        ["organization_id", "responsible_person_id"],
        ["organization_id", "id"],
    )
    op.create_index(
        "ix_findings_org_responsible_contractor",
        "findings",
        ["organization_id", "responsible_contractor_id"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION hys_block_finalized_audit_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        DECLARE
            audit_status text;
        BEGIN
            IF TG_TABLE_NAME = 'audits' THEN
                IF TG_OP IN ('UPDATE', 'DELETE') AND OLD.status = 'FINALIZADA' THEN
                    RAISE EXCEPTION 'finalized audit is immutable';
                END IF;
                RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
            END IF;

            IF TG_OP = 'DELETE' THEN
                SELECT status INTO audit_status FROM audits
                WHERE organization_id = OLD.organization_id AND id = OLD.audit_id;
            ELSE
                SELECT status INTO audit_status FROM audits
                WHERE organization_id = NEW.organization_id AND id = NEW.audit_id;
            END IF;
            IF audit_status = 'FINALIZADA' THEN
                RAISE EXCEPTION 'controls of a finalized audit are immutable';
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END
        $function$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audits_finalized_immutable
        BEFORE UPDATE OR DELETE ON audits
        FOR EACH ROW EXECUTE FUNCTION hys_block_finalized_audit_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_controls_finalized_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON audit_controls
        FOR EACH ROW EXECUTE FUNCTION hys_block_finalized_audit_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_controls_finalized_immutable ON audit_controls")
    op.execute("DROP TRIGGER IF EXISTS audits_finalized_immutable ON audits")
    op.execute("DROP FUNCTION IF EXISTS hys_block_finalized_audit_mutation()")

    op.drop_index("ix_findings_org_responsible_contractor", table_name="findings")
    op.drop_constraint(
        "fk_findings_org_responsible_person_people", "findings", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_findings_org_responsible_contractor_contractors", "findings", type_="foreignkey"
    )
    op.drop_column("findings", "responsible_person_id")
    op.drop_column("findings", "responsible_contractor_id")

    op.drop_constraint(
        "valid_function_code",
        "worksite_functional_assignments",
        type_="check",
    )
    op.create_check_constraint(
        "valid_function_code",
        "worksite_functional_assignments",
        "function_code IN ("
        "'RESPONSABLE_HYS_PROYECTO', 'AUDITOR_DELEGADO_PROYECTO', "
        "'RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL', 'TECNICO_HYS_CONTRATISTA_PRINCIPAL')",
    )
    # A downgrade must not discard project personnel that intentionally have no
    # contractor association. Restore the previous constraint only after an
    # explicit data migration assigns those rows to a contractor.
