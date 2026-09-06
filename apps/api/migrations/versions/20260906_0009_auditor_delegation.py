"""Replace the project auditor function and persist delegation provenance.

Revision ID: 20260906_0009
Revises: 20260905_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.naming import conv

revision: str = "20260906_0009"
down_revision: str | None = "20260905_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "valid_function_code",
        "worksite_functional_assignments",
        type_="check",
    )
    op.execute(
        sa.text(
            """
            UPDATE worksite_functional_assignments
            SET function_code = 'AUDITOR'
            WHERE function_code = 'AUDITOR_DELEGADO_PROYECTO'
            """
        )
    )
    op.add_column(
        "worksite_functional_assignments",
        sa.Column("delegated_by_assignment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_wfa_org_worksite_delegated_by_assignment",
        "worksite_functional_assignments",
        "worksite_functional_assignments",
        ["organization_id", "worksite_id", "delegated_by_assignment_id"],
        ["organization_id", "worksite_id", "id"],
    )
    op.create_check_constraint(
        "valid_function_code",
        "worksite_functional_assignments",
        "function_code IN ("
        "'RESPONSABLE_HYS_PROYECTO', 'AUDITOR', "
        "'RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL', "
        "'TECNICO_HYS_CONTRATISTA_PRINCIPAL', "
        "'RESPONSABLE_HYS_CONTRATISTA', 'TECNICO_HYS_CONTRATISTA')",
    )
    op.create_check_constraint(
        conv("ck_wfa_project_contractor_forbidden"),
        "worksite_functional_assignments",
        "function_code NOT IN ('RESPONSABLE_HYS_PROYECTO', 'AUDITOR') "
        "OR represented_contractor_id IS NULL",
    )
    op.create_check_constraint(
        conv("ck_wfa_delegation_only_auditor"),
        "worksite_functional_assignments",
        "function_code = 'AUDITOR' OR delegated_by_assignment_id IS NULL",
    )
    op.create_check_constraint(
        conv("ck_wfa_delegation_cannot_be_self"),
        "worksite_functional_assignments",
        "delegated_by_assignment_id IS NULL OR delegated_by_assignment_id <> id",
    )


def downgrade() -> None:
    op.drop_constraint(
        conv("ck_wfa_delegation_cannot_be_self"),
        "worksite_functional_assignments",
        type_="check",
    )
    op.drop_constraint(
        conv("ck_wfa_delegation_only_auditor"),
        "worksite_functional_assignments",
        type_="check",
    )
    op.drop_constraint(
        conv("ck_wfa_project_contractor_forbidden"),
        "worksite_functional_assignments",
        type_="check",
    )
    op.drop_constraint(
        "valid_function_code",
        "worksite_functional_assignments",
        type_="check",
    )
    op.drop_constraint(
        "fk_wfa_org_worksite_delegated_by_assignment",
        "worksite_functional_assignments",
        type_="foreignkey",
    )
    op.drop_column("worksite_functional_assignments", "delegated_by_assignment_id")
    op.execute(
        sa.text(
            """
            UPDATE worksite_functional_assignments
            SET function_code = 'AUDITOR_DELEGADO_PROYECTO'
            WHERE function_code = 'AUDITOR'
            """
        )
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
