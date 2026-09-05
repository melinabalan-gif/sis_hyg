"""Complete the pilot QA correction package without introducing authentication.

Revision ID: 20260905_0007
Revises: 20260904_0006

All new history tables are tenant isolated and append-only from the runtime
role. Existing rows are preserved; nullable columns are used for safe legacy
backfill. Binary file storage remains outside this pilot revision.
"""

# ruff: noqa: S608 — identifiers and privileges come only from migration constants.

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260905_0007"
down_revision: str | None = "20260904_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_SETTING = "NULLIF(current_setting('app.current_organization_id', true), '')::uuid"


def _secure_table(table: str, privileges: str = "SELECT, INSERT") -> None:
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
        f"""
        DO $migration$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hys_app') THEN
                RAISE EXCEPTION 'required runtime role hys_app does not exist';
            END IF;
            GRANT {privileges} ON TABLE {table} TO hys_app;
        END
        $migration$
        """
    )


def upgrade() -> None:
    op.execute(
        "UPDATE worksite_contractors SET participation_type = 'CONTRACTOR' "
        "WHERE participation_type = 'SUBCONTRACTOR'"
    )
    op.drop_constraint("valid_participation_type", "worksite_contractors", type_="check")
    op.create_check_constraint(
        "valid_participation_type",
        "worksite_contractors",
        "participation_type IN ('PRINCIPAL', 'CONTRACTOR')",
    )
    op.add_column("worksites", sa.Column("country", sa.String(120), nullable=True))
    op.add_column("worksites", sa.Column("province", sa.String(120), nullable=True))
    op.add_column("worksites", sa.Column("municipality", sa.String(120), nullable=True))
    op.add_column("worksites", sa.Column("created_by_actor_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "worksite_stages",
        sa.Column("status", sa.String(16), server_default=sa.text("'ACTIVA'"), nullable=False),
    )
    op.create_check_constraint(
        "valid_status",
        "worksite_stages",
        "status IN ('PLANIFICADA', 'ACTIVA', 'CERRADA')",
    )

    op.add_column("documents", sa.Column("uploaded_by_actor_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("documents", sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True))
    # Use explicit SQL so the physical names remain stable independently of
    # Alembic/SQLAlchemy naming-convention handling.
    op.execute("ALTER TABLE documents DROP CONSTRAINT ck_documents_valid_review_status")
    op.execute(
        """
        ALTER TABLE documents
        ADD CONSTRAINT ck_documents_valid_review_status
        CHECK (review_status IN ('PENDIENTE', 'APROBADO', 'OBSERVADO', 'RECHAZADO'))
        """
    )
    op.execute("ALTER TABLE document_versions DROP CONSTRAINT ck_document_versions_valid_review_status")
    op.execute(
        """
        ALTER TABLE document_versions
        ADD CONSTRAINT ck_document_versions_valid_review_status
        CHECK (review_status IN ('PENDIENTE', 'APROBADO', 'OBSERVADO', 'RECHAZADO'))
        """
    )

    op.add_column("findings", sa.Column("affected_contractor_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_findings_org_affected_contractor_contractors",
        "findings",
        "contractors",
        ["organization_id", "affected_contractor_id"],
        ["organization_id", "id"],
    )
    op.create_index(
        "ix_findings_org_affected_contractor",
        "findings",
        ["organization_id", "affected_contractor_id"],
    )

    for column in ("machine_type", "brand", "model", "license_plate"):
        op.add_column("machines", sa.Column(column, sa.String(120 if column != "license_plate" else 32), nullable=True))
    op.add_column("machines", sa.Column("owner_contractor_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("machines", sa.Column("operator_person_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_machines_org_owner_contractor_contractors",
        "machines",
        "contractors",
        ["organization_id", "owner_contractor_id"],
        ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_machines_org_operator_person_people",
        "machines",
        "people",
        ["organization_id", "operator_person_id"],
        ["organization_id", "id"],
    )
    op.add_column(
        "machine_inspections",
        sa.Column("checklist", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column("machine_inspections", sa.Column("evidence_note", sa.Text(), nullable=True))
    op.add_column("machine_inspections", sa.Column("inspector_function", sa.String(120), nullable=True))

    op.create_table(
        "worksite_stage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_worksite_stage_events"),
        sa.UniqueConstraint("organization_id", "id", name="uq_worksite_stage_events_organization_id_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "stage_id"],
            ["worksite_stages.organization_id", "worksite_stages.id"],
            name="fk_worksite_stage_events_org_stage_worksite_stages",
        ),
        sa.CheckConstraint("btrim(event_type) <> ''", name="event_type_not_blank"),
        sa.CheckConstraint("btrim(detail) <> ''", name="detail_not_blank"),
    )
    op.create_index(
        "ix_worksite_stage_events_org_stage_created",
        "worksite_stage_events",
        ["organization_id", "stage_id", "created_at"],
    )

    op.create_table(
        "person_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("worksite_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("function_label", sa.String(160), nullable=False),
        sa.Column("verified_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("observation", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_person_verifications"),
        sa.UniqueConstraint("organization_id", "id", name="uq_person_verifications_organization_id_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "person_id"],
            ["people.organization_id", "people.id"],
            name="fk_person_verifications_org_person_people",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "worksite_id"],
            ["worksites.organization_id", "worksites.id"],
            name="fk_person_verifications_org_worksite_worksites",
        ),
        sa.CheckConstraint(
            "status IN ('PENDIENTE_VERIFICACION', 'HABILITADO', 'DOCUMENTACION_INCOMPLETA', 'NO_HABILITADO')",
            name="valid_status",
        ),
        sa.CheckConstraint("btrim(function_label) <> ''", name="function_label_not_blank"),
    )
    op.create_index(
        "ix_person_verifications_org_worksite_person",
        "person_verifications",
        ["organization_id", "worksite_id", "person_id"],
    )

    op.create_table(
        "document_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_function", sa.String(120), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("foundation", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_document_reviews"),
        sa.UniqueConstraint("organization_id", "id", name="uq_document_reviews_organization_id_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name="fk_document_reviews_org_document_documents",
        ),
        sa.CheckConstraint("result IN ('APROBADO', 'OBSERVADO', 'RECHAZADO')", name="valid_result"),
        sa.CheckConstraint("btrim(foundation) <> ''", name="foundation_not_blank"),
    )
    op.create_index(
        "ix_document_reviews_org_document_created",
        "document_reviews",
        ["organization_id", "document_id", "reviewed_at"],
    )

    op.create_table(
        "machine_inspection_validations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inspection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("validated_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("validator_function", sa.String(120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_machine_inspection_validations"),
        sa.UniqueConstraint("organization_id", "id", name="uq_machine_inspection_validations_organization_id_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "inspection_id"],
            ["machine_inspections.organization_id", "machine_inspections.id"],
            name="fk_machine_inspection_validations_org_inspection",
        ),
        sa.CheckConstraint("btrim(notes) <> ''", name="notes_not_blank"),
    )

    _secure_table("worksite_stage_events")
    _secure_table("person_verifications")
    _secure_table("document_reviews")
    _secure_table("machine_inspection_validations")


def downgrade() -> None:
    op.drop_constraint("valid_participation_type", "worksite_contractors", type_="check")
    op.create_check_constraint(
        "valid_participation_type",
        "worksite_contractors",
        "participation_type IN ('PRINCIPAL', 'CONTRACTOR', 'SUBCONTRACTOR')",
    )
    for table in ("machine_inspection_validations", "document_reviews", "person_verifications"):
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE {table} FROM hys_app")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.drop_table("machine_inspection_validations")
    op.drop_index("ix_document_reviews_org_document_created", table_name="document_reviews")
    op.drop_table("document_reviews")
    op.drop_index("ix_person_verifications_org_worksite_person", table_name="person_verifications")
    op.drop_table("person_verifications")

    op.execute("REVOKE ALL PRIVILEGES ON TABLE worksite_stage_events FROM hys_app")
    op.execute("DROP POLICY IF EXISTS worksite_stage_events_tenant_isolation ON worksite_stage_events")
    op.drop_index("ix_worksite_stage_events_org_stage_created", table_name="worksite_stage_events")
    op.drop_table("worksite_stage_events")

    op.drop_column("machine_inspections", "inspector_function")
    op.drop_column("machine_inspections", "evidence_note")
    op.drop_column("machine_inspections", "checklist")
    op.drop_constraint("valid_status", "worksite_stages", type_="check")
    op.drop_column("worksite_stages", "status")
    op.drop_constraint("fk_machines_org_operator_person_people", "machines", type_="foreignkey")
    op.drop_constraint(
        "fk_machines_org_owner_contractor_contractors", "machines", type_="foreignkey"
    )
    for column in ("operator_person_id", "owner_contractor_id", "license_plate", "model", "brand", "machine_type"):
        op.drop_column("machines", column)
    op.execute(
        "ALTER TABLE document_versions DROP CONSTRAINT ck_document_versions_valid_review_status"
    )
    op.execute(
        """
        ALTER TABLE document_versions
        ADD CONSTRAINT ck_document_versions_valid_review_status
        CHECK (review_status IN ('PENDIENTE', 'APROBADO', 'RECHAZADO'))
        """
    )
    op.execute("ALTER TABLE documents DROP CONSTRAINT ck_documents_valid_review_status")
    op.execute(
        """
        ALTER TABLE documents
        ADD CONSTRAINT ck_documents_valid_review_status
        CHECK (review_status IN ('PENDIENTE', 'APROBADO', 'RECHAZADO'))
        """
    )
    op.drop_column("documents", "uploaded_at")
    op.drop_column("documents", "uploaded_by_actor_id")
    op.drop_index("ix_findings_org_affected_contractor", table_name="findings")
    op.drop_constraint(
        "fk_findings_org_affected_contractor_contractors", "findings", type_="foreignkey"
    )
    op.drop_column("findings", "affected_contractor_id")
    op.drop_column("worksites", "created_by_actor_id")
    op.drop_column("worksites", "municipality")
    op.drop_column("worksites", "province")
    op.drop_column("worksites", "country")
