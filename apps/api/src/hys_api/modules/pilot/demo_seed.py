"""Idempotent deterministic dataset for the synthetic pilot walkthrough."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import create_async_engine

from hys_api.api.dependencies import PILOT_ACTORS, PILOT_ORGANIZATION_ID
from hys_api.core.config import Settings
from hys_api.modules.pilot.models import (
    Audit,
    AuditControl,
    Contractor,
    ContractorDocument,
    Document,
    DocumentVersion,
    Finding,
    FindingControl,
    FindingEvent,
    Machine,
    MachineInspection,
    MachineWorksiteAssignment,
    Person,
    PersonAssignment,
    WorksiteContractor,
    WorksiteDocument,
    WorksiteFunctionalAssignment,
    WorksiteStage,
)
from hys_api.modules.worksites.models import Worksite

ORGANIZATION_ID = PILOT_ORGANIZATION_ID
WORKSITE_ID = UUID("00000000-0000-4000-8000-000000001001")
AUDITOR_ID = PILOT_ACTORS["auditor"].id
TECNICO_ID = PILOT_ACTORS["tecnico"].id
RESPONSABLE_ID = PILOT_ACTORS["responsable"].id
RESPONSABLE_SUPLENTE_ID = PILOT_ACTORS["responsable-suplente"].id
SEED_AT = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def _id(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def insert(table: Any, values: Any, *, update_columns: tuple[str, ...] = ()) -> Any:
    """Insert deterministic rows and repair only their fixed mutable projection."""

    statement = postgres_insert(table).values(values)
    if not update_columns:
        return statement.on_conflict_do_nothing(index_elements=[table.__table__.c.id])
    return statement.on_conflict_do_update(
        index_elements=[table.__table__.c.id],
        set_={column: getattr(statement.excluded, column) for column in update_columns},
    )


async def seed_demo() -> bool:
    migration_url = os.environ.get("HYS_MIGRATION_DATABASE_URL")
    if migration_url is None:
        raise RuntimeError("HYS_MIGRATION_DATABASE_URL must be configured for demo seeding")
    settings = Settings(
        database_url=SecretStr(migration_url),
        migration_database_url=SecretStr(migration_url),
    )

    engine = create_async_engine(settings.sqlalchemy_migration_database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_organization_id', :organization_id, true)"),
                {"organization_id": str(ORGANIZATION_ID)},
            )
            created = (
                await connection.scalar(
                    select(Worksite.id).where(
                        Worksite.organization_id == ORGANIZATION_ID,
                        Worksite.id == WORKSITE_ID,
                    )
                )
                is None
            )
            await connection.execute(
                insert(
                    Worksite,
                    {
                        "id": WORKSITE_ID,
                        "organization_id": ORGANIZATION_ID,
                        "code": "DEMO-OBRA-001",
                        "name": "Obra Demo Sintética",
                        "jurisdiction": "Provincia sintética",
                        "status": "ACTIVE",
                        "created_at": SEED_AT,
                        "updated_at": SEED_AT,
                        "version": 1,
                    },
                    update_columns=(
                        "code",
                        "name",
                        "jurisdiction",
                        "status",
                        "updated_at",
                        "version",
                    ),
                )
            )
            await connection.execute(
                insert(
                    WorksiteStage,
                    {
                        "id": _id(1002),
                        "organization_id": ORGANIZATION_ID,
                        "worksite_id": WORKSITE_ID,
                        "code": "STG-DEMO-001",
                        "name": "Montaje inicial",
                        "started_on": date(2026, 9, 1),
                        "sector": "Sector sintético norte",
                        "notes": "Etapa de demostración persistida.",
                        "created_at": SEED_AT,
                        "updated_at": SEED_AT,
                    },
                )
            )
            contractor_id = _id(1003)
            await connection.execute(
                insert(
                    Contractor,
                    {
                        "id": contractor_id,
                        "organization_id": ORGANIZATION_ID,
                        "legal_name": "Contratista Demo Sintético",
                        "trade": "Montaje sintético",
                        "created_at": SEED_AT,
                        "updated_at": SEED_AT,
                        "version": 1,
                    },
                    update_columns=("legal_name", "trade", "updated_at", "deleted_at", "version"),
                )
            )
            await connection.execute(
                insert(
                    WorksiteContractor,
                    {
                        "id": _id(1004),
                        "organization_id": ORGANIZATION_ID,
                        "worksite_id": WORKSITE_ID,
                        "contractor_id": contractor_id,
                        "participation_type": "PRINCIPAL",
                        "started_on": date(2026, 9, 1),
                        "created_at": SEED_AT,
                    },
                    update_columns=(
                        "worksite_id",
                        "contractor_id",
                        "participation_type",
                        "parent_contracting_company_id",
                        "started_on",
                        "ended_on",
                    ),
                )
            )
            secondary_contractor_id = _id(1034)
            secondary_subcontractor_id = _id(1035)
            await connection.execute(
                insert(
                    Contractor,
                    [
                        {
                            "id": secondary_contractor_id,
                            "organization_id": ORGANIZATION_ID,
                            "legal_name": "Contratista Demo A",
                            "trade": "Instalaciones sintéticas",
                            "created_at": SEED_AT,
                            "updated_at": SEED_AT,
                            "version": 1,
                        },
                        {
                            "id": secondary_subcontractor_id,
                            "organization_id": ORGANIZATION_ID,
                            "legal_name": "Contratista Demo B",
                            "trade": "Servicios sintéticos",
                            "created_at": SEED_AT,
                            "updated_at": SEED_AT,
                            "version": 1,
                        },
                    ],
                    update_columns=("legal_name", "trade", "updated_at", "deleted_at", "version"),
                )
            )
            await connection.execute(
                insert(
                    WorksiteContractor,
                    [
                        {
                            "id": _id(1036),
                            "organization_id": ORGANIZATION_ID,
                            "worksite_id": WORKSITE_ID,
                            "contractor_id": secondary_contractor_id,
                            "participation_type": "CONTRACTOR",
                            "parent_contracting_company_id": contractor_id,
                            "started_on": date(2026, 9, 1),
                            "created_at": SEED_AT,
                        },
                        {
                            "id": _id(1037),
                            "organization_id": ORGANIZATION_ID,
                            "worksite_id": WORKSITE_ID,
                            "contractor_id": secondary_subcontractor_id,
                            "participation_type": "CONTRACTOR",
                            "parent_contracting_company_id": secondary_contractor_id,
                            "started_on": date(2026, 9, 1),
                            "created_at": SEED_AT,
                        },
                    ],
                    update_columns=(
                        "worksite_id",
                        "contractor_id",
                        "participation_type",
                        "parent_contracting_company_id",
                        "started_on",
                        "ended_on",
                    ),
                )
            )
            person_id = _id(1005)
            await connection.execute(
                insert(
                    Person,
                    {
                        "id": person_id,
                        "organization_id": ORGANIZATION_ID,
                        "display_name": "Persona Demo 01",
                        "role_label": "Operador sintético",
                        "created_at": SEED_AT,
                        "updated_at": SEED_AT,
                        "version": 1,
                    },
                    update_columns=(
                        "display_name",
                        "role_label",
                        "profession_code",
                        "updated_at",
                        "deleted_at",
                        "version",
                    ),
                )
            )
            await connection.execute(
                insert(
                    PersonAssignment,
                    {
                        "id": _id(1006),
                        "organization_id": ORGANIZATION_ID,
                        "worksite_id": WORKSITE_ID,
                        "contractor_id": contractor_id,
                        "person_id": person_id,
                        "started_on": date(2026, 9, 1),
                        "created_at": SEED_AT,
                    },
                    update_columns=(
                        "worksite_id",
                        "contractor_id",
                        "person_id",
                        "started_on",
                        "ended_on",
                    ),
                )
            )
            project_professional_id = _id(1030)
            delegated_auditor_person_id = _id(1031)
            contractor_professional_id = _id(1032)
            contractor_technician_id = _id(1033)
            await connection.execute(
                insert(
                    Person,
                    [
                        {
                            "id": project_professional_id,
                            "organization_id": ORGANIZATION_ID,
                            "display_name": "Profesional HYS proyecto demo",
                            "role_label": "Responsable HYS de proyecto",
                            "profession_code": "LICENCIADO_HYS",
                            "created_at": SEED_AT,
                            "updated_at": SEED_AT,
                            "version": 1,
                        },
                        {
                            "id": delegated_auditor_person_id,
                            "organization_id": ORGANIZATION_ID,
                            "display_name": "Auditor técnico demo",
                            "role_label": "Auditor",
                            "profession_code": "TECNICO_HYS",
                            "created_at": SEED_AT,
                            "updated_at": SEED_AT,
                            "version": 1,
                        },
                        {
                            "id": contractor_professional_id,
                            "organization_id": ORGANIZATION_ID,
                            "display_name": "Profesional HYS contratista demo",
                            "role_label": "Responsable HYS contratista principal",
                            "profession_code": "LICENCIADO_HYS",
                            "created_at": SEED_AT,
                            "updated_at": SEED_AT,
                            "version": 1,
                        },
                        {
                            "id": contractor_technician_id,
                            "organization_id": ORGANIZATION_ID,
                            "display_name": "Técnico HYS contratista demo",
                            "role_label": "Técnico HYS contratista principal",
                            "profession_code": "TECNICO_HYS",
                            "created_at": SEED_AT,
                            "updated_at": SEED_AT,
                            "version": 1,
                        },
                    ],
                    update_columns=(
                        "display_name",
                        "role_label",
                        "profession_code",
                        "updated_at",
                        "deleted_at",
                        "version",
                    ),
                )
            )
            await connection.execute(
                insert(
                    PersonAssignment,
                    [
                        {
                            "id": _id(1043),
                            "organization_id": ORGANIZATION_ID,
                            "worksite_id": WORKSITE_ID,
                            "contractor_id": None,
                            "person_id": project_professional_id,
                            "started_on": date(2026, 9, 1),
                            "ended_on": None,
                            "created_at": SEED_AT,
                        },
                        {
                            "id": _id(1044),
                            "organization_id": ORGANIZATION_ID,
                            "worksite_id": WORKSITE_ID,
                            "contractor_id": None,
                            "person_id": delegated_auditor_person_id,
                            "started_on": date(2026, 9, 1),
                            "ended_on": None,
                            "created_at": SEED_AT,
                        },
                        {
                            "id": _id(1045),
                            "organization_id": ORGANIZATION_ID,
                            "worksite_id": WORKSITE_ID,
                            "contractor_id": contractor_id,
                            "person_id": contractor_professional_id,
                            "started_on": date(2026, 9, 1),
                            "ended_on": None,
                            "created_at": SEED_AT,
                        },
                        {
                            "id": _id(1046),
                            "organization_id": ORGANIZATION_ID,
                            "worksite_id": WORKSITE_ID,
                            "contractor_id": contractor_id,
                            "person_id": contractor_technician_id,
                            "started_on": date(2026, 9, 1),
                            "ended_on": None,
                            "created_at": SEED_AT,
                        },
                    ],
                    update_columns=(
                        "worksite_id",
                        "contractor_id",
                        "person_id",
                        "started_on",
                        "ended_on",
                    ),
                )
            )
            await connection.execute(
                insert(
                    WorksiteFunctionalAssignment,
                    [
                        {
                            "id": _id(1038),
                            "organization_id": ORGANIZATION_ID,
                            "worksite_id": WORKSITE_ID,
                            "actor_id": RESPONSABLE_ID,
                            "person_id": project_professional_id,
                            "function_code": "RESPONSABLE_HYS_PROYECTO",
                            "represented_contractor_id": None,
                            "delegated_by_assignment_id": None,
                            "permission_scope": "WORKSITE",
                            "valid_from": date(2026, 9, 1),
                            "version": 1,
                            "created_at": SEED_AT,
                        },
                        {
                            "id": _id(1039),
                            "organization_id": ORGANIZATION_ID,
                            "worksite_id": WORKSITE_ID,
                            "actor_id": AUDITOR_ID,
                            "person_id": delegated_auditor_person_id,
                            "function_code": "AUDITOR",
                            "represented_contractor_id": None,
                            "delegated_by_assignment_id": _id(1038),
                            "permission_scope": "WORKSITE",
                            "valid_from": date(2026, 9, 1),
                            "version": 1,
                            "created_at": SEED_AT,
                        },
                        {
                            "id": _id(1040),
                            "organization_id": ORGANIZATION_ID,
                            "worksite_id": WORKSITE_ID,
                            "actor_id": RESPONSABLE_ID,
                            "person_id": project_professional_id,
                            "function_code": "AUDITOR",
                            "represented_contractor_id": None,
                            "delegated_by_assignment_id": None,
                            "permission_scope": "WORKSITE",
                            "valid_from": date(2026, 9, 1),
                            "version": 1,
                            "created_at": SEED_AT,
                        },
                        {
                            "id": _id(1041),
                            "organization_id": ORGANIZATION_ID,
                            "worksite_id": WORKSITE_ID,
                            "actor_id": RESPONSABLE_SUPLENTE_ID,
                            "person_id": contractor_professional_id,
                            "function_code": "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL",
                            "represented_contractor_id": contractor_id,
                            "delegated_by_assignment_id": None,
                            "permission_scope": "WORKSITE",
                            "valid_from": date(2026, 9, 1),
                            "version": 1,
                            "created_at": SEED_AT,
                        },
                        {
                            "id": _id(1042),
                            "organization_id": ORGANIZATION_ID,
                            "worksite_id": WORKSITE_ID,
                            "actor_id": TECNICO_ID,
                            "person_id": contractor_technician_id,
                            "function_code": "TECNICO_HYS_CONTRATISTA_PRINCIPAL",
                            "represented_contractor_id": contractor_id,
                            "delegated_by_assignment_id": None,
                            "permission_scope": "WORKSITE",
                            "valid_from": date(2026, 9, 1),
                            "version": 1,
                            "created_at": SEED_AT,
                        },
                    ],
                    update_columns=(
                        "worksite_id",
                        "actor_id",
                        "person_id",
                        "function_code",
                        "represented_contractor_id",
                        "delegated_by_assignment_id",
                        "permission_scope",
                        "valid_from",
                        "valid_to",
                        "version",
                    ),
                )
            )
            machine_id = _id(1007)
            await connection.execute(
                insert(
                    Machine,
                    {
                        "id": machine_id,
                        "organization_id": ORGANIZATION_ID,
                        "internal_code": "MAQ-DEMO-001",
                        "description": "Equipo de izaje sintético",
                        "status": "OPERATIVA",
                        "created_at": SEED_AT,
                        "updated_at": SEED_AT,
                        "version": 1,
                    },
                    update_columns=(
                        "internal_code",
                        "description",
                        "status",
                        "updated_at",
                        "deleted_at",
                        "version",
                    ),
                )
            )
            await connection.execute(
                insert(
                    MachineWorksiteAssignment,
                    {
                        "id": _id(1008),
                        "organization_id": ORGANIZATION_ID,
                        "worksite_id": WORKSITE_ID,
                        "contractor_id": contractor_id,
                        "machine_id": machine_id,
                        "started_on": date(2026, 9, 1),
                        "created_at": SEED_AT,
                    },
                    update_columns=(
                        "worksite_id",
                        "contractor_id",
                        "machine_id",
                        "started_on",
                        "ended_on",
                    ),
                )
            )
            await connection.execute(
                insert(
                    MachineInspection,
                    {
                        "id": _id(1009),
                        "organization_id": ORGANIZATION_ID,
                        "machine_id": machine_id,
                        "worksite_id": WORKSITE_ID,
                        "resulting_status": "OPERATIVA",
                        "reason": "Inspección inicial sintética aprobada.",
                        "checklist": {
                            "brakes": "CUMPLE",
                            "lights": "CUMPLE",
                            "reverse_alarm": "CUMPLE",
                            "horn": "CUMPLE",
                            "tires": "CUMPLE",
                            "mirrors": "CUMPLE",
                            "seat_belt": "CUMPLE",
                            "fire_extinguisher": "CUMPLE",
                            "warning_lights": "CUMPLE",
                            "leaks": "CUMPLE",
                            "guards": "CUMPLE",
                            "signage": "CUMPLE",
                            "specific_devices": "NO_APLICA",
                        },
                        "actor_id": TECNICO_ID,
                        "inspected_at": SEED_AT,
                    },
                    update_columns=("actor_id",),
                )
            )

            document_id = _id(1010)
            await connection.execute(
                insert(
                    Document,
                    {
                        "id": document_id,
                        "organization_id": ORGANIZATION_ID,
                        "title": "Seguro técnico demo",
                        "document_type": "SEGURO",
                        "review_status": "APROBADO",
                        "valid_from": date(2026, 9, 1),
                        "expires_on": date(2026, 9, 20),
                        "notes": "Metadata sintética para validar próximo vencimiento.",
                        "created_at": SEED_AT,
                        "updated_at": SEED_AT,
                        "version": 1,
                    },
                    update_columns=(
                        "title",
                        "document_type",
                        "review_status",
                        "valid_from",
                        "expires_on",
                        "notes",
                        "updated_at",
                        "version",
                    ),
                )
            )
            await connection.execute(
                insert(
                    DocumentVersion,
                    {
                        "id": _id(1011),
                        "organization_id": ORGANIZATION_ID,
                        "document_id": document_id,
                        "version_number": 1,
                        "title": "Seguro técnico demo",
                        "document_type": "SEGURO",
                        "review_status": "APROBADO",
                        "valid_from": date(2026, 9, 1),
                        "expires_on": date(2026, 9, 20),
                        "notes": "Metadata sintética para validar próximo vencimiento.",
                        "actor_id": TECNICO_ID,
                        "created_at": SEED_AT,
                    },
                    update_columns=("actor_id",),
                )
            )
            await connection.execute(
                insert(
                    WorksiteDocument,
                    {
                        "id": _id(1012),
                        "organization_id": ORGANIZATION_ID,
                        "document_id": document_id,
                        "worksite_id": WORKSITE_ID,
                        "created_at": SEED_AT,
                    },
                )
            )
            contractor_document_id = _id(1013)
            await connection.execute(
                insert(
                    Document,
                    {
                        "id": contractor_document_id,
                        "organization_id": ORGANIZATION_ID,
                        "title": "Constancia contratista demo",
                        "document_type": "CONSTANCIA",
                        "review_status": "APROBADO",
                        "valid_from": date(2026, 1, 1),
                        "expires_on": date(2026, 8, 31),
                        "notes": "Metadata sintética vencida.",
                        "created_at": SEED_AT,
                        "updated_at": SEED_AT,
                        "version": 1,
                    },
                    update_columns=(
                        "title",
                        "document_type",
                        "review_status",
                        "valid_from",
                        "expires_on",
                        "notes",
                        "updated_at",
                        "version",
                    ),
                )
            )
            await connection.execute(
                insert(
                    DocumentVersion,
                    {
                        "id": _id(1014),
                        "organization_id": ORGANIZATION_ID,
                        "document_id": contractor_document_id,
                        "version_number": 1,
                        "title": "Constancia contratista demo",
                        "document_type": "CONSTANCIA",
                        "review_status": "APROBADO",
                        "valid_from": date(2026, 1, 1),
                        "expires_on": date(2026, 8, 31),
                        "notes": "Metadata sintética vencida.",
                        "actor_id": TECNICO_ID,
                        "created_at": SEED_AT,
                    },
                    update_columns=("actor_id",),
                )
            )
            await connection.execute(
                insert(
                    ContractorDocument,
                    {
                        "id": _id(1015),
                        "organization_id": ORGANIZATION_ID,
                        "document_id": contractor_document_id,
                        "contractor_id": contractor_id,
                        "created_at": SEED_AT,
                    },
                )
            )
            audit_id = _id(1017)
            existing_audit_status = await connection.scalar(
                select(Audit.status).where(
                    Audit.organization_id == ORGANIZATION_ID,
                    Audit.id == audit_id,
                )
            )
            audit_is_finalized = existing_audit_status == "FINALIZADA"
            if not audit_is_finalized:
                await connection.execute(
                    insert(
                        Audit,
                        {
                            "id": audit_id,
                            "organization_id": ORGANIZATION_ID,
                            "worksite_id": WORKSITE_ID,
                            "status": "EN_CURSO",
                            "author_actor_id": AUDITOR_ID,
                            "editor_actor_id": AUDITOR_ID,
                            "started_at": SEED_AT,
                            "finalized_at": None,
                            "created_at": SEED_AT,
                            "updated_at": SEED_AT,
                            "version": 2,
                            "control_catalog_version_id": UUID(
                                "00000000-0000-4000-8000-000000000102"
                            ),
                            "auditor_actor_id": AUDITOR_ID,
                            "auditor_assignment_id": _id(1039),
                            "associated_professional_person_id": project_professional_id,
                            "audit_date": SEED_AT.date(),
                        },
                        update_columns=(
                            "worksite_id",
                            "status",
                            "author_actor_id",
                            "editor_actor_id",
                            "started_at",
                            "finalized_at",
                            "updated_at",
                            "auditor_actor_id",
                            "auditor_assignment_id",
                            "associated_professional_person_id",
                            "audit_date",
                        ),
                    )
                )
            control_ok_id = _id(1018)
            control_finding_id = _id(1019)
            control_na_id = _id(1020)
            if not audit_is_finalized:
                await connection.execute(
                    insert(
                        AuditControl,
                        [
                            {
                                "id": control_ok_id,
                                "organization_id": ORGANIZATION_ID,
                                "audit_id": audit_id,
                                "catalog_code": "SYN-CIRCULACION-001",
                                "catalog_title": (
                                    "Circulación y señalización interna - control sintético"
                                ),
                                "result": "CUMPLE",
                                "reason": None,
                                "recorded_by_actor_id": AUDITOR_ID,
                                "recorded_at": SEED_AT,
                            },
                            {
                                "id": control_finding_id,
                                "organization_id": ORGANIZATION_ID,
                                "audit_id": audit_id,
                                "catalog_code": "SYN-EPP-001",
                                "catalog_title": (
                                    "Elementos de protección personal - control sintético"
                                ),
                                "result": "NO_CUMPLE",
                                "reason": "Se requiere completar la entrega sintética.",
                                "recorded_by_actor_id": AUDITOR_ID,
                                "recorded_at": SEED_AT,
                            },
                            {
                                "id": control_na_id,
                                "organization_id": ORGANIZATION_ID,
                                "audit_id": audit_id,
                                "catalog_code": "SYN-ORDEN-001",
                                "catalog_title": (
                                    "Orden y condiciones generales - control sintético"
                                ),
                                "result": "NO_APLICA",
                                "reason": "No aplica al sector sintético de esta demostración.",
                                "recorded_by_actor_id": AUDITOR_ID,
                                "recorded_at": SEED_AT,
                            },
                        ],
                        update_columns=("recorded_by_actor_id",),
                    )
                )
                await connection.execute(
                    text(
                        "UPDATE audits SET status = 'FINALIZADA', finalized_at = :finalized_at, "
                        "updated_at = :updated_at WHERE organization_id = :organization_id "
                        "AND id = :audit_id"
                    ),
                    {
                        "finalized_at": SEED_AT,
                        "updated_at": SEED_AT,
                        "organization_id": ORGANIZATION_ID,
                        "audit_id": audit_id,
                    },
                )
            finding_id = _id(1021)
            await connection.execute(
                insert(
                    Finding,
                    {
                        "id": finding_id,
                        "organization_id": ORGANIZATION_ID,
                        "worksite_id": WORKSITE_ID,
                        "audit_id": audit_id,
                        "title": "Elementos de protección personal - control sintético",
                        "description": (
                            "Completar la entrega de EPP sintético y conservar evidencia."
                        ),
                        "status": "ABIERTO",
                        "severity_catalog_version_id": UUID("00000000-0000-4000-8000-000000000202"),
                        "severity_code": "MEDIA",
                        "severity_label": "Media sintética",
                        "affected_contractor_id": contractor_id,
                        "due_at": datetime(2026, 9, 18, 12, 0, tzinfo=UTC),
                        "created_by_actor_id": AUDITOR_ID,
                        "created_at": SEED_AT,
                        "updated_at": SEED_AT,
                        "version": 1,
                    },
                    update_columns=("created_by_actor_id",),
                )
            )
            await connection.execute(
                insert(
                    FindingControl,
                    {
                        "id": _id(1022),
                        "organization_id": ORGANIZATION_ID,
                        "finding_id": finding_id,
                        "audit_control_id": control_finding_id,
                        "created_at": SEED_AT,
                    },
                )
            )
            await connection.execute(
                insert(
                    FindingEvent,
                    {
                        "id": _id(1023),
                        "organization_id": ORGANIZATION_ID,
                        "finding_id": finding_id,
                        "event_type": "CREATED_FROM_CONTROL",
                        "to_status": "ABIERTO",
                        "actor_id": AUDITOR_ID,
                        "detail": "Desvío demo creado desde un control NO_CUMPLE.",
                        "created_at": SEED_AT,
                    },
                    update_columns=("actor_id",),
                )
            )
    finally:
        await engine.dispose()
    return created


def main() -> int:
    created = asyncio.run(seed_demo())
    print("Synthetic demo dataset seeded" if created else "Synthetic demo dataset already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
