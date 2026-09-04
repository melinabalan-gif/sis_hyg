"""Crea la persistencia tenant-aware del flujo vertical sintético del piloto.

Revision ID: 20260903_0002
Revises: 20260902_0001
Create Date: 2026-09-03 00:00:00

Compatibilidad: revisión aditiva; la API anterior puede seguir operando durante
la migración. Rollback: elimina exclusivamente datos/tablas del piloto; requiere
que la organización sintética no conserve obras creadas después del upgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260903_0002"
down_revision: str | None = "20260902_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_SETTING = "NULLIF(current_setting('app.current_organization_id', true), '')::uuid"
_PILOT_ORGANIZATION_ID = "00000000-0000-4000-8000-000000000001"
_PILOT_PUBLISHED_AT = "2026-09-03T00:00:00+00:00"

_PILOT_TABLES = (
    "contractors",
    "worksite_contractors",
    "people",
    "person_assignments",
    "machines",
    "machine_worksite_assignments",
    "machine_inspections",
    "documents",
    "worksite_documents",
    "contractor_documents",
    "person_documents",
    "machine_documents",
    "control_catalog_versions",
    "severity_catalog_versions",
    "audits",
    "audit_controls",
    "findings",
    "finding_controls",
    "corrections",
    "verifications",
    "finding_events",
)

_MUTABLE_TABLES = (
    "contractors",
    "worksite_contractors",
    "people",
    "person_assignments",
    "machines",
    "machine_worksite_assignments",
    "documents",
    "audits",
    "audit_controls",
    "findings",
)

_APPEND_ONLY_TABLES = (
    "machine_inspections",
    "worksite_documents",
    "contractor_documents",
    "person_documents",
    "machine_documents",
    "finding_controls",
    "corrections",
    "verifications",
    "finding_events",
)

_READ_ONLY_TABLES = (
    "control_catalog_versions",
    "severity_catalog_versions",
)


def _tenant_table_items(
    table_name: str,
    *items: sa.SchemaItem,
) -> tuple[sa.SchemaItem, ...]:
    return (
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        *items,
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=f"fk_{table_name}_organization_id_organizations",
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{table_name}"),
        sa.UniqueConstraint("organization_id", "id", name=f"uq_{table_name}_organization_id_id"),
    )


def _create_tables() -> None:
    op.create_table(
        "contractors",
        *_tenant_table_items(
            "contractors",
            sa.Column("legal_name", sa.String(length=200), nullable=False),
            sa.Column("trade", sa.String(length=120), nullable=False),
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
                "btrim(legal_name) <> ''", name=op.f("ck_contractors_legal_name_not_blank")
            ),
            sa.CheckConstraint("btrim(trade) <> ''", name=op.f("ck_contractors_trade_not_blank")),
            sa.UniqueConstraint(
                "organization_id",
                "legal_name",
                name="uq_contractors_organization_id_legal_name",
            ),
        ),
    )
    op.create_index(
        "ix_contractors_organization_id_deleted_at",
        "contractors",
        ["organization_id", "deleted_at"],
        unique=False,
    )

    op.create_table(
        "people",
        *_tenant_table_items(
            "people",
            sa.Column("display_name", sa.String(length=200), nullable=False),
            sa.Column("role_label", sa.String(length=120), nullable=False),
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
                "btrim(display_name) <> ''", name=op.f("ck_people_display_name_not_blank")
            ),
            sa.CheckConstraint(
                "btrim(role_label) <> ''", name=op.f("ck_people_role_label_not_blank")
            ),
        ),
    )
    op.create_index(
        "ix_people_organization_id_deleted_at",
        "people",
        ["organization_id", "deleted_at"],
        unique=False,
    )

    op.create_table(
        "machines",
        *_tenant_table_items(
            "machines",
            sa.Column("internal_code", sa.String(length=64), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column(
                "status",
                sa.String(length=32),
                server_default=sa.text("'OPERATIVA'"),
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
            sa.CheckConstraint(
                "status IN ('OPERATIVA', 'CON_OBSERVACIONES', 'FUERA_DE_SERVICIO')",
                name=op.f("ck_machines_valid_status"),
            ),
            sa.CheckConstraint(
                "btrim(internal_code) <> ''",
                name=op.f("ck_machines_internal_code_not_blank"),
            ),
            sa.CheckConstraint(
                "btrim(description) <> ''", name=op.f("ck_machines_description_not_blank")
            ),
            sa.UniqueConstraint(
                "organization_id",
                "internal_code",
                name="uq_machines_organization_id_internal_code",
            ),
        ),
    )
    op.create_index(
        "ix_machines_organization_id_status",
        "machines",
        ["organization_id", "status"],
        unique=False,
    )

    op.create_table(
        "documents",
        *_tenant_table_items(
            "documents",
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("document_type", sa.String(length=100), nullable=False),
            sa.Column(
                "review_status",
                sa.String(length=32),
                server_default=sa.text("'PENDIENTE'"),
                nullable=False,
            ),
            sa.Column("valid_from", sa.Date(), nullable=True),
            sa.Column("expires_on", sa.Date(), nullable=True),
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
            sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
            sa.CheckConstraint(
                "review_status IN ('PENDIENTE', 'APROBADO', 'RECHAZADO')",
                name=op.f("ck_documents_valid_review_status"),
            ),
            sa.CheckConstraint(
                "expires_on IS NULL OR valid_from IS NULL OR expires_on >= valid_from",
                name=op.f("ck_documents_valid_date_range"),
            ),
            sa.CheckConstraint("btrim(title) <> ''", name=op.f("ck_documents_title_not_blank")),
            sa.CheckConstraint(
                "btrim(document_type) <> ''",
                name=op.f("ck_documents_document_type_not_blank"),
            ),
        ),
    )
    op.create_index(
        "ix_documents_org_review_expires",
        "documents",
        ["organization_id", "review_status", "expires_on"],
        unique=False,
    )

    op.create_table(
        "control_catalog_versions",
        *_tenant_table_items(
            "control_catalog_versions",
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column(
                "published_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "btrim(code) <> ''",
                name=op.f("ck_control_catalog_versions_code_not_blank"),
            ),
            sa.CheckConstraint(
                "btrim(title) <> ''",
                name=op.f("ck_control_catalog_versions_title_not_blank"),
            ),
            sa.CheckConstraint(
                "version_number > 0",
                name=op.f("ck_control_catalog_versions_positive_version_number"),
            ),
            sa.UniqueConstraint(
                "organization_id",
                "code",
                "version_number",
                name="uq_control_catalog_versions_org_code_version",
            ),
        ),
    )
    op.create_index(
        "ix_control_catalog_versions_org_code",
        "control_catalog_versions",
        ["organization_id", "code"],
        unique=False,
    )

    op.create_table(
        "severity_catalog_versions",
        *_tenant_table_items(
            "severity_catalog_versions",
            sa.Column("code", sa.String(length=16), nullable=False),
            sa.Column("label", sa.String(length=100), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("default_due_days", sa.Integer(), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column(
                "published_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "code IN ('BAJA', 'MEDIA', 'ALTA', 'CRITICA')",
                name=op.f("ck_severity_catalog_versions_valid_code"),
            ),
            sa.CheckConstraint(
                "btrim(label) <> ''",
                name=op.f("ck_severity_catalog_versions_label_not_blank"),
            ),
            sa.CheckConstraint(
                "sort_order >= 0",
                name=op.f("ck_severity_catalog_versions_nonnegative_sort_order"),
            ),
            sa.CheckConstraint(
                "default_due_days >= 0",
                name=op.f("ck_severity_catalog_versions_nonnegative_default_due_days"),
            ),
            sa.CheckConstraint(
                "version_number > 0",
                name=op.f("ck_severity_catalog_versions_positive_version_number"),
            ),
            sa.UniqueConstraint(
                "organization_id",
                "code",
                "version_number",
                name="uq_severity_catalog_versions_org_code_version",
            ),
        ),
    )
    op.create_index(
        "ix_severity_catalog_versions_org_code",
        "severity_catalog_versions",
        ["organization_id", "code"],
        unique=False,
    )

    op.create_table(
        "worksite_contractors",
        *_tenant_table_items(
            "worksite_contractors",
            sa.Column("worksite_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("contractor_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("started_on", sa.Date(), nullable=False),
            sa.Column("ended_on", sa.Date(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "ended_on IS NULL OR ended_on > started_on",
                name=op.f("ck_worksite_contractors_valid_date_range"),
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "worksite_id"],
                ["worksites.organization_id", "worksites.id"],
                name="fk_worksite_contractors_org_worksite_worksites",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "contractor_id"],
                ["contractors.organization_id", "contractors.id"],
                name="fk_worksite_contractors_org_contractor_contractors",
            ),
        ),
    )
    op.create_index(
        "ix_worksite_contractors_org_worksite_ended",
        "worksite_contractors",
        ["organization_id", "worksite_id", "ended_on"],
        unique=False,
    )

    op.create_table(
        "person_assignments",
        *_tenant_table_items(
            "person_assignments",
            sa.Column("worksite_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("contractor_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("started_on", sa.Date(), nullable=False),
            sa.Column("ended_on", sa.Date(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "ended_on IS NULL OR ended_on > started_on",
                name=op.f("ck_person_assignments_valid_date_range"),
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "worksite_id"],
                ["worksites.organization_id", "worksites.id"],
                name="fk_person_assignments_org_worksite_worksites",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "contractor_id"],
                ["contractors.organization_id", "contractors.id"],
                name="fk_person_assignments_org_contractor_contractors",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "person_id"],
                ["people.organization_id", "people.id"],
                name="fk_person_assignments_org_person_people",
            ),
        ),
    )
    op.create_index(
        "ix_person_assignments_org_worksite_ended",
        "person_assignments",
        ["organization_id", "worksite_id", "ended_on"],
        unique=False,
    )

    op.create_table(
        "machine_worksite_assignments",
        *_tenant_table_items(
            "machine_worksite_assignments",
            sa.Column("worksite_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("contractor_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("machine_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("started_on", sa.Date(), nullable=False),
            sa.Column("ended_on", sa.Date(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "ended_on IS NULL OR ended_on > started_on",
                name=op.f("ck_machine_worksite_assignments_valid_date_range"),
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "worksite_id"],
                ["worksites.organization_id", "worksites.id"],
                name="fk_machine_worksite_assignments_org_worksite_worksites",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "contractor_id"],
                ["contractors.organization_id", "contractors.id"],
                name="fk_machine_worksite_assignments_org_contractor_contractors",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "machine_id"],
                ["machines.organization_id", "machines.id"],
                name="fk_machine_worksite_assignments_org_machine_machines",
            ),
        ),
    )
    op.create_index(
        "ix_machine_worksite_assignments_org_worksite_ended",
        "machine_worksite_assignments",
        ["organization_id", "worksite_id", "ended_on"],
        unique=False,
    )

    op.create_table(
        "machine_inspections",
        *_tenant_table_items(
            "machine_inspections",
            sa.Column("machine_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("worksite_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("resulting_status", sa.String(length=32), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "inspected_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "resulting_status IN ('OPERATIVA', 'CON_OBSERVACIONES', 'FUERA_DE_SERVICIO')",
                name=op.f("ck_machine_inspections_valid_resulting_status"),
            ),
            sa.CheckConstraint(
                "btrim(reason) <> ''", name=op.f("ck_machine_inspections_reason_not_blank")
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "machine_id"],
                ["machines.organization_id", "machines.id"],
                name="fk_machine_inspections_org_machine_machines",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "worksite_id"],
                ["worksites.organization_id", "worksites.id"],
                name="fk_machine_inspections_org_worksite_worksites",
            ),
        ),
    )
    op.create_index(
        "ix_machine_inspections_org_worksite_inspected",
        "machine_inspections",
        ["organization_id", "worksite_id", "inspected_at"],
        unique=False,
    )

    _create_document_association_tables()
    _create_audit_and_finding_tables()


def _create_document_association_tables() -> None:
    associations = (
        (
            "worksite_documents",
            "worksite_id",
            "worksites",
            "fk_worksite_documents_org_worksite_worksites",
            "ix_worksite_documents_org_worksite",
        ),
        (
            "contractor_documents",
            "contractor_id",
            "contractors",
            "fk_contractor_documents_org_contractor_contractors",
            "ix_contractor_documents_org_contractor",
        ),
        (
            "person_documents",
            "person_id",
            "people",
            "fk_person_documents_org_person_people",
            "ix_person_documents_org_person",
        ),
        (
            "machine_documents",
            "machine_id",
            "machines",
            "fk_machine_documents_org_machine_machines",
            "ix_machine_documents_org_machine",
        ),
    )
    for table_name, subject_column, subject_table, subject_fk, index_name in associations:
        op.create_table(
            table_name,
            *_tenant_table_items(
                table_name,
                sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
                sa.Column(subject_column, postgresql.UUID(as_uuid=True), nullable=False),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.text("now()"),
                    nullable=False,
                ),
                sa.ForeignKeyConstraint(
                    ["organization_id", "document_id"],
                    ["documents.organization_id", "documents.id"],
                    name=f"fk_{table_name}_org_document_documents",
                ),
                sa.ForeignKeyConstraint(
                    ["organization_id", subject_column],
                    [f"{subject_table}.organization_id", f"{subject_table}.id"],
                    name=subject_fk,
                ),
                sa.UniqueConstraint("document_id", name=f"uq_{table_name}_document_id"),
            ),
        )
        op.create_index(
            index_name,
            table_name,
            ["organization_id", subject_column],
            unique=False,
        )


def _create_audit_and_finding_tables() -> None:
    op.create_table(
        "audits",
        *_tenant_table_items(
            "audits",
            sa.Column("worksite_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "status",
                sa.String(length=32),
                server_default=sa.text("'EN_CURSO'"),
                nullable=False,
            ),
            sa.Column("author_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("editor_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
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
            sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
            sa.Column("control_catalog_version_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.CheckConstraint(
                "status IN ('EN_CURSO', 'FINALIZADA')",
                name=op.f("ck_audits_valid_status"),
            ),
            sa.CheckConstraint(
                "(status = 'EN_CURSO' AND finalized_at IS NULL) OR "
                "(status = 'FINALIZADA' AND finalized_at IS NOT NULL)",
                name=op.f("ck_audits_status_matches_finalized_at"),
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "worksite_id"],
                ["worksites.organization_id", "worksites.id"],
                name="fk_audits_org_worksite_worksites",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "control_catalog_version_id"],
                ["control_catalog_versions.organization_id", "control_catalog_versions.id"],
                name="fk_audits_org_control_catalog_control_catalog_versions",
            ),
        ),
    )
    op.create_index(
        "ix_audits_org_worksite_status",
        "audits",
        ["organization_id", "worksite_id", "status"],
        unique=False,
    )

    op.create_table(
        "audit_controls",
        *_tenant_table_items(
            "audit_controls",
            sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("catalog_code", sa.String(length=64), nullable=False),
            sa.Column("catalog_title", sa.String(length=200), nullable=False),
            sa.Column("result", sa.String(length=32), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("recorded_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "recorded_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
            sa.CheckConstraint(
                "result IN ('CUMPLE', 'NO_CUMPLE', 'NO_APLICA', 'NO_VERIFICADO')",
                name=op.f("ck_audit_controls_valid_result"),
            ),
            sa.CheckConstraint(
                "result NOT IN ('NO_APLICA', 'NO_VERIFICADO') "
                "OR NULLIF(btrim(reason), '') IS NOT NULL",
                name=op.f("ck_audit_controls_reason_required_for_unresolved_result"),
            ),
            sa.CheckConstraint(
                "btrim(catalog_code) <> ''",
                name=op.f("ck_audit_controls_catalog_code_not_blank"),
            ),
            sa.CheckConstraint(
                "btrim(catalog_title) <> ''",
                name=op.f("ck_audit_controls_catalog_title_not_blank"),
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "audit_id"],
                ["audits.organization_id", "audits.id"],
                name="fk_audit_controls_org_audit_audits",
            ),
            sa.UniqueConstraint(
                "organization_id",
                "audit_id",
                "catalog_code",
                name="uq_audit_controls_org_audit_catalog_code",
            ),
        ),
    )
    op.create_index(
        "ix_audit_controls_org_audit_result",
        "audit_controls",
        ["organization_id", "audit_id", "result"],
        unique=False,
    )

    op.create_table(
        "findings",
        *_tenant_table_items(
            "findings",
            sa.Column("worksite_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column(
                "status",
                sa.String(length=32),
                server_default=sa.text("'ABIERTO'"),
                nullable=False,
            ),
            sa.Column("severity_catalog_version_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("severity_code", sa.String(length=16), nullable=False),
            sa.Column("severity_label", sa.String(length=100), nullable=False),
            sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
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
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
            sa.CheckConstraint(
                "status IN ('ABIERTO', 'EN_CORRECCION', 'PENDIENTE_VERIFICACION', 'CERRADO')",
                name=op.f("ck_findings_valid_status"),
            ),
            sa.CheckConstraint(
                "severity_code IN ('BAJA', 'MEDIA', 'ALTA', 'CRITICA')",
                name=op.f("ck_findings_valid_severity_code"),
            ),
            sa.CheckConstraint(
                "(status = 'CERRADO' AND closed_at IS NOT NULL) OR "
                "(status <> 'CERRADO' AND closed_at IS NULL)",
                name=op.f("ck_findings_status_matches_closed_at"),
            ),
            sa.CheckConstraint("btrim(title) <> ''", name=op.f("ck_findings_title_not_blank")),
            sa.CheckConstraint(
                "btrim(description) <> ''", name=op.f("ck_findings_description_not_blank")
            ),
            sa.CheckConstraint(
                "btrim(severity_label) <> ''",
                name=op.f("ck_findings_severity_label_not_blank"),
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "worksite_id"],
                ["worksites.organization_id", "worksites.id"],
                name="fk_findings_org_worksite_worksites",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "audit_id"],
                ["audits.organization_id", "audits.id"],
                name="fk_findings_org_audit_audits",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "severity_catalog_version_id"],
                ["severity_catalog_versions.organization_id", "severity_catalog_versions.id"],
                name="fk_findings_org_severity_severity_catalog_versions",
            ),
        ),
    )
    op.create_index(
        "ix_findings_org_worksite_status",
        "findings",
        ["organization_id", "worksite_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_findings_org_status_due_at",
        "findings",
        ["organization_id", "status", "due_at"],
        unique=False,
    )

    _create_finding_history_tables()


def _create_finding_history_tables() -> None:
    op.create_table(
        "finding_controls",
        *_tenant_table_items(
            "finding_controls",
            sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("audit_control_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "finding_id"],
                ["findings.organization_id", "findings.id"],
                name="fk_finding_controls_org_finding_findings",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "audit_control_id"],
                ["audit_controls.organization_id", "audit_controls.id"],
                name="fk_finding_controls_org_audit_control_audit_controls",
            ),
            sa.UniqueConstraint("audit_control_id", name="uq_finding_controls_audit_control_id"),
        ),
    )
    op.create_index(
        "ix_finding_controls_org_finding",
        "finding_controls",
        ["organization_id", "finding_id"],
        unique=False,
    )

    op.create_table(
        "corrections",
        *_tenant_table_items(
            "corrections",
            sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("evidence_note", sa.Text(), nullable=False),
            sa.Column("authored_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "btrim(description) <> ''",
                name=op.f("ck_corrections_description_not_blank"),
            ),
            sa.CheckConstraint(
                "btrim(evidence_note) <> ''",
                name=op.f("ck_corrections_evidence_note_not_blank"),
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "finding_id"],
                ["findings.organization_id", "findings.id"],
                name="fk_corrections_org_finding_findings",
            ),
        ),
    )
    op.create_index(
        "ix_corrections_org_finding_created",
        "corrections",
        ["organization_id", "finding_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "verifications",
        *_tenant_table_items(
            "verifications",
            sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("decision", sa.String(length=16), nullable=False),
            sa.Column("notes", sa.Text(), nullable=False),
            sa.Column("verified_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "decision IN ('ACEPTADA', 'RECHAZADA')",
                name=op.f("ck_verifications_valid_decision"),
            ),
            sa.CheckConstraint(
                "decision <> 'RECHAZADA' OR btrim(notes) <> ''",
                name=op.f("ck_verifications_notes_required_for_rejection"),
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "finding_id"],
                ["findings.organization_id", "findings.id"],
                name="fk_verifications_org_finding_findings",
            ),
        ),
    )
    op.create_index(
        "ix_verifications_org_finding_created",
        "verifications",
        ["organization_id", "finding_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "finding_events",
        *_tenant_table_items(
            "finding_events",
            sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("from_status", sa.String(length=32), nullable=True),
            sa.Column("to_status", sa.String(length=32), nullable=False),
            sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "from_status IS NULL OR from_status IN "
                "('ABIERTO', 'EN_CORRECCION', 'PENDIENTE_VERIFICACION', 'CERRADO')",
                name=op.f("ck_finding_events_valid_from_status"),
            ),
            sa.CheckConstraint(
                "to_status IN ('ABIERTO', 'EN_CORRECCION', 'PENDIENTE_VERIFICACION', 'CERRADO')",
                name=op.f("ck_finding_events_valid_to_status"),
            ),
            sa.CheckConstraint(
                "btrim(event_type) <> ''",
                name=op.f("ck_finding_events_event_type_not_blank"),
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "finding_id"],
                ["findings.organization_id", "findings.id"],
                name="fk_finding_events_org_finding_findings",
            ),
        ),
    )
    op.create_index(
        "ix_finding_events_org_finding_created",
        "finding_events",
        ["organization_id", "finding_id", "created_at"],
        unique=False,
    )


def _configure_rls_and_grants() -> None:
    for table_name in _PILOT_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_isolation ON {table_name}
            AS PERMISSIVE FOR ALL
            USING (organization_id = {_TENANT_SETTING})
            WITH CHECK (organization_id = {_TENANT_SETTING})
            """
        )
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE {table_name} FROM PUBLIC")

    op.execute(
        """
        DO $migration$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hys_app') THEN
                RAISE EXCEPTION 'required runtime role hys_app does not exist';
            END IF;
        END
        $migration$
        """
    )
    for table_name in _MUTABLE_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {table_name} TO hys_app")
    for table_name in _APPEND_ONLY_TABLES:
        op.execute(f"GRANT SELECT, INSERT ON TABLE {table_name} TO hys_app")
    for table_name in _READ_ONLY_TABLES:
        op.execute(f"GRANT SELECT ON TABLE {table_name} TO hys_app")


def _seed_synthetic_catalogs() -> None:
    op.execute(
        sa.text(
            "SELECT set_config('app.current_organization_id', :organization_id, true)"
        ).bindparams(organization_id=_PILOT_ORGANIZATION_ID)
    )
    op.execute(
        sa.text(
            """
            INSERT INTO organizations
                (id, name, slug, timezone, created_at, updated_at, version)
            VALUES
                (
                    CAST(:organization_id AS uuid),
                    :name,
                    :slug,
                    'America/Argentina/Buenos_Aires',
                    CAST(:published_at AS timestamptz),
                    CAST(:published_at AS timestamptz),
                    1
                )
            """
        ).bindparams(
            organization_id=_PILOT_ORGANIZATION_ID,
            name="Piloto HYS — datos sintéticos",
            slug="piloto-hys-sintetico",
            published_at=_PILOT_PUBLISHED_AT,
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO control_catalog_versions
                (id, organization_id, code, title, version_number, published_at)
            VALUES
                (
                    CAST(:id AS uuid),
                    CAST(:organization_id AS uuid),
                    'SYN-ORDEN-001',
                    :title,
                    1,
                    CAST(:published_at AS timestamptz)
                )
            """
        ).bindparams(
            id="00000000-0000-4000-8000-000000000101",
            organization_id=_PILOT_ORGANIZATION_ID,
            title="Orden y condiciones generales — control sintético",
            published_at=_PILOT_PUBLISHED_AT,
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO severity_catalog_versions
                (
                    id,
                    organization_id,
                    code,
                    label,
                    sort_order,
                    default_due_days,
                    version_number,
                    published_at
                )
            VALUES
                (CAST(:low_id AS uuid), CAST(:organization_id AS uuid),
                 'BAJA', 'Baja sintética', 10, 30, 1, CAST(:published_at AS timestamptz)),
                (CAST(:medium_id AS uuid), CAST(:organization_id AS uuid),
                 'MEDIA', 'Media sintética', 20, 14, 1, CAST(:published_at AS timestamptz)),
                (CAST(:high_id AS uuid), CAST(:organization_id AS uuid),
                 'ALTA', 'Alta sintética', 30, 7, 1, CAST(:published_at AS timestamptz)),
                (CAST(:critical_id AS uuid), CAST(:organization_id AS uuid),
                 'CRITICA', 'Crítica sintética', 40, 1, 1, CAST(:published_at AS timestamptz))
            """
        ).bindparams(
            low_id="00000000-0000-4000-8000-000000000201",
            medium_id="00000000-0000-4000-8000-000000000202",
            high_id="00000000-0000-4000-8000-000000000203",
            critical_id="00000000-0000-4000-8000-000000000204",
            organization_id=_PILOT_ORGANIZATION_ID,
            published_at=_PILOT_PUBLISHED_AT,
        )
    )
    op.execute("SELECT set_config('app.current_organization_id', '', true)")


def upgrade() -> None:
    _create_tables()
    _configure_rls_and_grants()
    _seed_synthetic_catalogs()


def downgrade() -> None:
    op.execute(
        sa.text(
            "SELECT set_config('app.current_organization_id', :organization_id, true)"
        ).bindparams(organization_id=_PILOT_ORGANIZATION_ID)
    )
    for table_name in _PILOT_TABLES:
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE {table_name} FROM hys_app")
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}")

    for table_name in (
        "finding_events",
        "verifications",
        "corrections",
        "finding_controls",
        "findings",
        "audit_controls",
        "audits",
        "machine_documents",
        "person_documents",
        "contractor_documents",
        "worksite_documents",
        "machine_inspections",
        "machine_worksite_assignments",
        "person_assignments",
        "worksite_contractors",
        "severity_catalog_versions",
        "control_catalog_versions",
        "documents",
        "machines",
        "people",
        "contractors",
    ):
        op.drop_table(table_name)

    op.execute(
        sa.text(
            """
            DELETE FROM organizations AS organization
            WHERE organization.id = CAST(:organization_id AS uuid)
              AND NOT EXISTS (
                  SELECT 1
                  FROM worksites
                  WHERE worksites.organization_id = organization.id
              )
            """
        ).bindparams(organization_id=_PILOT_ORGANIZATION_ID)
    )
    op.execute("SELECT set_config('app.current_organization_id', '', true)")
