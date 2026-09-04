"""Idempotent deterministic dataset for the synthetic pilot walkthrough."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import create_async_engine

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
    WorksiteStage,
)
from hys_api.modules.worksites.models import Worksite

ORGANIZATION_ID = UUID("00000000-0000-4000-8000-000000000001")
WORKSITE_ID = UUID("00000000-0000-4000-8000-000000001001")
AUDITOR_ID = UUID("00000000-0000-0000-0000-000000000001")
TECNICO_ID = UUID("00000000-0000-0000-0000-000000000002")
SEED_AT = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def _id(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


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
            exists = await connection.scalar(
                select(Worksite.id).where(
                    Worksite.organization_id == ORGANIZATION_ID,
                    Worksite.id == WORKSITE_ID,
                )
            )
            if exists is not None:
                return False

            await connection.execute(
                insert(Worksite),
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
            )
            await connection.execute(
                insert(WorksiteStage),
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
            contractor_id = _id(1003)
            await connection.execute(
                insert(Contractor),
                {
                    "id": contractor_id,
                    "organization_id": ORGANIZATION_ID,
                    "legal_name": "Contratista Demo Sintético",
                    "trade": "Montaje sintético",
                    "created_at": SEED_AT,
                    "updated_at": SEED_AT,
                    "version": 1,
                },
            )
            await connection.execute(
                insert(WorksiteContractor),
                {
                    "id": _id(1004),
                    "organization_id": ORGANIZATION_ID,
                    "worksite_id": WORKSITE_ID,
                    "contractor_id": contractor_id,
                    "started_on": date(2026, 9, 1),
                    "created_at": SEED_AT,
                },
            )
            person_id = _id(1005)
            await connection.execute(
                insert(Person),
                {
                    "id": person_id,
                    "organization_id": ORGANIZATION_ID,
                    "display_name": "Persona Demo 01",
                    "role_label": "Operador sintético",
                    "created_at": SEED_AT,
                    "updated_at": SEED_AT,
                    "version": 1,
                },
            )
            await connection.execute(
                insert(PersonAssignment),
                {
                    "id": _id(1006),
                    "organization_id": ORGANIZATION_ID,
                    "worksite_id": WORKSITE_ID,
                    "contractor_id": contractor_id,
                    "person_id": person_id,
                    "started_on": date(2026, 9, 1),
                    "created_at": SEED_AT,
                },
            )
            machine_id = _id(1007)
            await connection.execute(
                insert(Machine),
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
            )
            await connection.execute(
                insert(MachineWorksiteAssignment),
                {
                    "id": _id(1008),
                    "organization_id": ORGANIZATION_ID,
                    "worksite_id": WORKSITE_ID,
                    "contractor_id": contractor_id,
                    "machine_id": machine_id,
                    "started_on": date(2026, 9, 1),
                    "created_at": SEED_AT,
                },
            )
            await connection.execute(
                insert(MachineInspection),
                {
                    "id": _id(1009),
                    "organization_id": ORGANIZATION_ID,
                    "machine_id": machine_id,
                    "worksite_id": WORKSITE_ID,
                    "resulting_status": "OPERATIVA",
                    "reason": "Inspección inicial sintética aprobada.",
                    "actor_id": TECNICO_ID,
                    "inspected_at": SEED_AT,
                },
            )

            document_id = _id(1010)
            await connection.execute(
                insert(Document),
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
            )
            await connection.execute(
                insert(DocumentVersion),
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
            )
            await connection.execute(
                insert(WorksiteDocument),
                {
                    "id": _id(1012),
                    "organization_id": ORGANIZATION_ID,
                    "document_id": document_id,
                    "worksite_id": WORKSITE_ID,
                    "created_at": SEED_AT,
                },
            )
            contractor_document_id = _id(1013)
            await connection.execute(
                insert(Document),
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
            )
            await connection.execute(
                insert(DocumentVersion),
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
            )
            await connection.execute(
                insert(ContractorDocument),
                {
                    "id": _id(1015),
                    "organization_id": ORGANIZATION_ID,
                    "document_id": contractor_document_id,
                    "contractor_id": contractor_id,
                    "created_at": SEED_AT,
                },
            )
            audit_id = _id(1017)
            await connection.execute(
                insert(Audit),
                {
                    "id": audit_id,
                    "organization_id": ORGANIZATION_ID,
                    "worksite_id": WORKSITE_ID,
                    "status": "FINALIZADA",
                    "author_actor_id": AUDITOR_ID,
                    "editor_actor_id": AUDITOR_ID,
                    "started_at": SEED_AT,
                    "finalized_at": SEED_AT,
                    "created_at": SEED_AT,
                    "updated_at": SEED_AT,
                    "version": 2,
                    "control_catalog_version_id": UUID("00000000-0000-4000-8000-000000000102"),
                },
            )
            control_ok_id = _id(1018)
            control_finding_id = _id(1019)
            control_na_id = _id(1020)
            await connection.execute(
                insert(AuditControl),
                [
                    {
                        "id": control_ok_id,
                        "organization_id": ORGANIZATION_ID,
                        "audit_id": audit_id,
                        "catalog_code": "SYN-CIRCULACION-001",
                        "catalog_title": "Circulación y señalización interna - control sintético",
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
                        "catalog_title": "Elementos de protección personal - control sintético",
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
                        "catalog_title": "Orden y condiciones generales - control sintético",
                        "result": "NO_APLICA",
                        "reason": "No aplica al sector sintético de esta demostración.",
                        "recorded_by_actor_id": AUDITOR_ID,
                        "recorded_at": SEED_AT,
                    },
                ],
            )
            finding_id = _id(1021)
            await connection.execute(
                insert(Finding),
                {
                    "id": finding_id,
                    "organization_id": ORGANIZATION_ID,
                    "worksite_id": WORKSITE_ID,
                    "audit_id": audit_id,
                    "title": "Elementos de protección personal - control sintético",
                    "description": "Completar la entrega de EPP sintético y conservar evidencia.",
                    "status": "ABIERTO",
                    "severity_catalog_version_id": UUID("00000000-0000-4000-8000-000000000202"),
                    "severity_code": "MEDIA",
                    "severity_label": "Media sintética",
                    "due_at": datetime(2026, 9, 18, 12, 0, tzinfo=UTC),
                    "created_by_actor_id": AUDITOR_ID,
                    "created_at": SEED_AT,
                    "updated_at": SEED_AT,
                    "version": 1,
                },
            )
            await connection.execute(
                insert(FindingControl),
                {
                    "id": _id(1022),
                    "organization_id": ORGANIZATION_ID,
                    "finding_id": finding_id,
                    "audit_control_id": control_finding_id,
                    "created_at": SEED_AT,
                },
            )
            await connection.execute(
                insert(FindingEvent),
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
            )
    finally:
        await engine.dispose()
    return True


def main() -> int:
    created = asyncio.run(seed_demo())
    print("Synthetic demo dataset seeded" if created else "Synthetic demo dataset already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
