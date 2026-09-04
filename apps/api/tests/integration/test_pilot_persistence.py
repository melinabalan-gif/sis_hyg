from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from hys_api.api.dependencies import PILOT_ACTORS, PILOT_ORGANIZATION_ID, PilotRequestContext
from hys_api.core.errors import ProblemException
from hys_api.db.tenant import AuthorizationContext, apply_authorization_context
from hys_api.modules.pilot.report import build_worksite_report_pdf
from hys_api.modules.pilot.schemas import (
    AuditControlCreate,
    ControlResult,
    CorrectionCreate,
    DocumentCreate,
    DocumentDisplayStatus,
    DocumentVersionCreate,
    MachineCreate,
    MachineInspectionCreate,
    SubjectKind,
    VerificationCreate,
    VerificationDecision,
    WorksiteCreate,
    derive_document_status,
)
from hys_api.modules.pilot.service import PilotService

pytestmark = pytest.mark.integration
PILOT_CONTROL_CATALOG_IDS = {
    UUID("00000000-0000-4000-8000-000000000101"),
    UUID("00000000-0000-4000-8000-000000000102"),
    UUID("00000000-0000-4000-8000-000000000103"),
}

PILOT_TABLES = {
    "audit_controls",
    "audits",
    "contractor_documents",
    "contractors",
    "control_catalog_versions",
    "corrections",
    "documents",
    "document_versions",
    "finding_controls",
    "finding_events",
    "findings",
    "machine_documents",
    "machine_inspections",
    "machine_worksite_assignments",
    "machines",
    "people",
    "person_assignments",
    "person_documents",
    "severity_catalog_versions",
    "verifications",
    "worksite_contractors",
    "worksite_documents",
    "worksite_stages",
}

MUTABLE_TABLES = {
    "audit_controls",
    "audits",
    "contractors",
    "documents",
    "findings",
    "machine_worksite_assignments",
    "machines",
    "people",
    "person_assignments",
    "worksite_contractors",
}

APPEND_ONLY_TABLES = {
    "contractor_documents",
    "corrections",
    "finding_controls",
    "finding_events",
    "machine_documents",
    "machine_inspections",
    "person_documents",
    "verifications",
    "worksite_documents",
    "worksite_stages",
    "document_versions",
}

READ_ONLY_TABLES = {"control_catalog_versions", "severity_catalog_versions"}


@pytest.mark.asyncio
async def test_pilot_seed_rls_and_policies(migrated_database: str) -> None:
    engine = create_async_engine(migrated_database)
    try:
        async with engine.connect() as connection:
            organization = (
                await connection.execute(
                    text("SELECT id, name, slug FROM organizations WHERE id = :organization_id"),
                    {"organization_id": PILOT_ORGANIZATION_ID},
                )
            ).one()
            control_catalog = (
                await connection.execute(
                    text(
                        "SELECT id, organization_id, code, version_number "
                        "FROM control_catalog_versions ORDER BY code"
                    )
                )
            ).all()
            severities = (
                await connection.execute(
                    text(
                        "SELECT code, sort_order, default_due_days, version_number "
                        "FROM severity_catalog_versions ORDER BY sort_order"
                    )
                )
            ).all()
            rls_rows = (
                await connection.execute(
                    text(
                        "SELECT relname, relrowsecurity, relforcerowsecurity "
                        "FROM pg_class WHERE relname = ANY(:tables)"
                    ),
                    {"tables": sorted(PILOT_TABLES)},
                )
            ).all()
            policy_rows = (
                await connection.execute(
                    text(
                        "SELECT tablename, policyname, cmd, qual, with_check "
                        "FROM pg_policies WHERE tablename = ANY(:tables)"
                    ),
                    {"tables": sorted(PILOT_TABLES)},
                )
            ).all()
    finally:
        await engine.dispose()

    assert organization == (
        PILOT_ORGANIZATION_ID,
        "Piloto HYS — datos sintéticos",
        "piloto-hys-sintetico",
    )
    assert {row[0] for row in control_catalog} == PILOT_CONTROL_CATALOG_IDS
    assert {(row[2], row[3]) for row in control_catalog} == {
        ("SYN-CIRCULACION-001", 1),
        ("SYN-EPP-001", 1),
        ("SYN-ORDEN-001", 1),
    }
    assert severities == [
        ("BAJA", 10, 30, 1),
        ("MEDIA", 20, 14, 1),
        ("ALTA", 30, 7, 1),
        ("CRITICA", 40, 1, 1),
    ]
    assert {row[0] for row in rls_rows} == PILOT_TABLES
    assert all(row[1] is True and row[2] is True for row in rls_rows)
    assert {row[0] for row in policy_rows} == PILOT_TABLES
    assert len(policy_rows) == len(PILOT_TABLES)
    for table_name, policy_name, command, using_expression, check_expression in policy_rows:
        assert policy_name == f"{table_name}_tenant_isolation"
        assert command == "ALL"
        assert "organization_id" in using_expression
        assert "current_setting" in using_expression
        assert "organization_id" in check_expression
        assert "current_setting" in check_expression


@pytest.mark.asyncio
async def test_pilot_tables_have_least_privilege_grants(
    migrated_database: str,
    app_database_url: str,
) -> None:
    owner_engine = create_async_engine(migrated_database)
    app_engine = create_async_engine(app_database_url)
    try:
        async with owner_engine.connect() as connection:
            public_grants = (
                await connection.execute(
                    text(
                        "SELECT table_name, privilege_type "
                        "FROM information_schema.table_privileges "
                        "WHERE table_schema = current_schema() AND grantee = 'PUBLIC' "
                        "AND table_name = ANY(:tables)"
                    ),
                    {"tables": sorted(PILOT_TABLES)},
                )
            ).all()
            app_grants = (
                await connection.execute(
                    text(
                        "SELECT table_name, privilege_type "
                        "FROM information_schema.table_privileges "
                        "WHERE table_schema = current_schema() AND grantee = 'hys_app' "
                        "AND table_name = ANY(:tables)"
                    ),
                    {"tables": sorted(PILOT_TABLES)},
                )
            ).all()
        async with app_engine.connect() as connection:
            identity = (await connection.execute(text("SELECT current_user, session_user"))).one()
    finally:
        await app_engine.dispose()
        await owner_engine.dispose()

    grants_by_table = {
        table_name: {
            privilege for granted_table, privilege in app_grants if granted_table == table_name
        }
        for table_name in PILOT_TABLES
    }
    assert public_grants == []
    assert identity == ("hys_app", "hys_app")
    assert all(grants_by_table[table] == {"SELECT", "INSERT", "UPDATE"} for table in MUTABLE_TABLES)
    assert all(grants_by_table[table] == {"SELECT", "INSERT"} for table in APPEND_ONLY_TABLES)
    assert all(grants_by_table[table] == {"SELECT"} for table in READ_ONLY_TABLES)
    assert all("DELETE" not in privileges for privileges in grants_by_table.values())


@pytest.mark.asyncio
async def test_pilot_composite_fks_and_rls_reject_cross_tenant_rows(
    migrated_database: str,
    app_database_url: str,
) -> None:
    owner_engine = create_async_engine(migrated_database)
    app_engine = create_async_engine(app_database_url)
    organization_a = UUID("30000000-0000-4000-8000-000000000001")
    organization_b = UUID("40000000-0000-4000-8000-000000000002")
    worksite_a = UUID("30000000-0000-4000-8000-000000000011")
    worksite_b = UUID("40000000-0000-4000-8000-000000000022")
    contractor_a = UUID("30000000-0000-4000-8000-000000000101")
    contractor_b = UUID("40000000-0000-4000-8000-000000000202")
    try:
        async with owner_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) VALUES "
                    "(:organization_a, 'Organización sintética FK A', 'syn-fk-a'), "
                    "(:organization_b, 'Organización sintética FK B', 'syn-fk-b')"
                ),
                {"organization_a": organization_a, "organization_b": organization_b},
            )
            await connection.execute(
                text(
                    "INSERT INTO worksites (id, organization_id, code, name) VALUES "
                    "(:worksite_a, :organization_a, 'SYN-FK-A', 'Obra sintética FK A'), "
                    "(:worksite_b, :organization_b, 'SYN-FK-B', 'Obra sintética FK B')"
                ),
                {
                    "worksite_a": worksite_a,
                    "organization_a": organization_a,
                    "worksite_b": worksite_b,
                    "organization_b": organization_b,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO contractors "
                    "(id, organization_id, legal_name, trade) VALUES "
                    "(:contractor_a, :organization_a, 'Contratista sintético FK A', 'SYN-A'), "
                    "(:contractor_b, :organization_b, 'Contratista sintético FK B', 'SYN-B')"
                ),
                {
                    "contractor_a": contractor_a,
                    "organization_a": organization_a,
                    "contractor_b": contractor_b,
                    "organization_b": organization_b,
                },
            )

        with pytest.raises(DBAPIError):
            async with owner_engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO worksite_contractors "
                        "(id, organization_id, worksite_id, contractor_id, started_on) "
                        "VALUES (:id, :organization_a, :worksite_b, :contractor_a, :started_on)"
                    ),
                    {
                        "id": UUID("30000000-0000-4000-8000-000000000999"),
                        "organization_a": organization_a,
                        "worksite_b": worksite_b,
                        "contractor_a": contractor_a,
                        "started_on": date(2026, 1, 1),
                    },
                )

        async with app_engine.begin() as connection:
            without_context = await connection.scalar(text("SELECT count(*) FROM contractors"))
        async with app_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_organization_id', :tenant, true)"),
                {"tenant": str(organization_a)},
            )
            visible_contractors = set(await connection.scalars(text("SELECT id FROM contractors")))

        with pytest.raises(DBAPIError):
            async with app_engine.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('app.current_organization_id', :tenant, true)"),
                    {"tenant": str(organization_a)},
                )
                await connection.execute(
                    text(
                        "INSERT INTO contractors "
                        "(id, organization_id, legal_name, trade) "
                        "VALUES (:id, :organization_b, 'Cruce sintético', 'SYN-X')"
                    ),
                    {
                        "id": UUID("40000000-0000-4000-8000-000000000999"),
                        "organization_b": organization_b,
                    },
                )
    finally:
        await app_engine.dispose()
        await owner_engine.dispose()

    assert without_context == 0
    assert visible_contractors == {contractor_a}


@pytest.mark.asyncio
async def test_worksite_stage_intervals_and_legacy_jurisdiction_default(
    migrated_database: str,
) -> None:
    engine = create_async_engine(migrated_database)
    worksite_id = UUID("50000000-0000-4000-8000-000000000011")
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO worksites (id, organization_id, code, name) "
                    "VALUES (:worksite_id, :organization_id, 'SYN-STAGES-001', 'Obra etapas')"
                ),
                {"worksite_id": worksite_id, "organization_id": PILOT_ORGANIZATION_ID},
            )
            jurisdiction = await connection.scalar(
                text("SELECT jurisdiction FROM worksites WHERE id = :worksite_id"),
                {"worksite_id": worksite_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO worksite_stages "
                    "(id, organization_id, worksite_id, code, name, started_on) "
                    "VALUES "
                    "('50000000-0000-4000-8000-000000000101', :organization_id, :worksite_id, "
                    "'STG-001', 'Preparación', '2026-09-01'), "
                    "('50000000-0000-4000-8000-000000000102', :organization_id, :worksite_id, "
                    "'STG-002', 'Montaje', '2026-09-15')"
                ),
                {"worksite_id": worksite_id, "organization_id": PILOT_ORGANIZATION_ID},
            )
            count = await connection.scalar(
                text("SELECT count(*) FROM worksite_stages WHERE worksite_id = :worksite_id"),
                {"worksite_id": worksite_id},
            )
    finally:
        await engine.dispose()

    assert jurisdiction == "SIN_ESPECIFICAR"
    assert count == 2

    engine = create_async_engine(migrated_database)
    try:
        with pytest.raises(DBAPIError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO worksite_stages "
                        "(id, organization_id, worksite_id, code, name, started_on, ended_on) "
                        "VALUES ('50000000-0000-4000-8000-000000000103', :organization_id, "
                        ":worksite_id, 'STG-003', 'Invertida', '2026-10-01', '2026-09-01')"
                    ),
                    {"worksite_id": worksite_id, "organization_id": PILOT_ORGANIZATION_ID},
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_document_versions_are_initial_sequenced_append_only_and_scoped(
    migrated_database: str,
) -> None:
    engine = create_async_engine(migrated_database)
    try:
        async with AsyncSession(engine) as session:
            async with session.begin():
                service = PilotService(
                    PilotRequestContext(actor=PILOT_ACTORS["tecnico"], session=session)
                )
                first_worksite = await service.create_worksite(
                    WorksiteCreate(
                        code="SYN-DOC-VERSIONS-A",
                        name="Obra de versiones A",
                        jurisdiction="Provincia sintética",
                    )
                )
                first = await service.create_document(
                    first_worksite.id,
                    DocumentCreate(
                        subject_kind=SubjectKind.WORKSITE,
                        subject_id=first_worksite.id,
                        title="Seguro inicial",
                        document_type="SEGURO",
                        review_status="APROBADO",
                        expires_on=date(2026, 9, 5),
                    ),
                )
                second = await service.create_document_version(
                    first_worksite.id,
                    first.id,
                    DocumentVersionCreate(
                        title="Seguro renovado",
                        document_type="SEGURO",
                        review_status="APROBADO",
                        valid_from=date(2026, 9, 1),
                        expires_on=date(2026, 12, 31),
                        notes="Renovación sintética",
                    ),
                )
                versions = (
                    await session.execute(
                        text(
                            "SELECT version_number, title FROM document_versions "
                            "WHERE document_id = :document_id ORDER BY version_number"
                        ),
                        {"document_id": first.id},
                    )
                ).all()
                second_worksite = await service.create_worksite(
                    WorksiteCreate(
                        code="SYN-DOC-VERSIONS-B",
                        name="Obra de versiones B",
                        jurisdiction="Provincia sintética",
                    )
                )

        assert first.version == 1
        assert [item.version_number for item in first.versions] == [1]
        assert second.version == 2
        assert second.title == "Seguro renovado"
        assert second.expires_on == date(2026, 12, 31)
        assert (
            derive_document_status(
                second.review_status,
                second.expires_on,
                today=date(2026, 9, 1),
            )
            is DocumentDisplayStatus.VIGENTE
        )
        assert (
            derive_document_status(
                first.review_status,
                first.expires_on,
                today=date(2026, 9, 1),
            )
            is DocumentDisplayStatus.POR_VENCER
        )
        assert [(row[0], row[1]) for row in versions] == [
            (1, "Seguro inicial"),
            (2, "Seguro renovado"),
        ]

        async with AsyncSession(engine) as session:
            async with session.begin():
                service = PilotService(
                    PilotRequestContext(actor=PILOT_ACTORS["tecnico"], session=session)
                )
                with pytest.raises(ProblemException) as raised:
                    await service.create_document_version(
                        second_worksite.id,
                        first.id,
                        DocumentVersionCreate(
                            title="Cruce de obra",
                            document_type="SEGURO",
                        ),
                    )
        assert raised.value.status == 404
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_machine_inspections_are_initial_and_append_only_transitions(
    migrated_database: str,
) -> None:
    engine = create_async_engine(migrated_database)
    try:
        async with AsyncSession(engine) as session:
            async with session.begin():
                service = PilotService(
                    PilotRequestContext(actor=PILOT_ACTORS["tecnico"], session=session)
                )
                worksite = await service.create_worksite(
                    WorksiteCreate(
                        code="SYN-MACHINE-INSPECTIONS",
                        name="Obra de inspecciones",
                        jurisdiction="Provincia sintética",
                    )
                )
                machine = await service.create_machine(
                    worksite.id,
                    MachineCreate(
                        internal_code="MAQ-INS-001",
                        description="Equipo sintético",
                        status="OPERATIVA",
                        reason="Inspección inicial aprobada",
                    ),
                )
                stopped = await service.record_machine_inspection(
                    worksite.id,
                    machine.id,
                    MachineInspectionCreate(
                        resulting_status="FUERA_DE_SERVICIO",
                        reason="Falla crítica detectada",
                    ),
                )
                recovered = await service.record_machine_inspection(
                    worksite.id,
                    machine.id,
                    MachineInspectionCreate(
                        resulting_status="OPERATIVA",
                        reason="Reparación verificada en reinspección",
                    ),
                )
                rows = (
                    await session.execute(
                        text(
                            "SELECT resulting_status, reason FROM machine_inspections "
                            "WHERE machine_id = :machine_id ORDER BY inspected_at, id"
                        ),
                        {"machine_id": machine.id},
                    )
                ).all()

        assert machine.version == 1
        assert stopped.status.value == "FUERA_DE_SERVICIO"
        assert recovered.status.value == "OPERATIVA"
        assert recovered.version == 3
        assert len(recovered.inspections) == 3
        assert {(item.resulting_status.value, item.reason) for item in recovered.inspections} == {
            ("OPERATIVA", "Inspección inicial aprobada"),
            ("FUERA_DE_SERVICIO", "Falla crítica detectada"),
            ("OPERATIVA", "Reparación verificada en reinspección"),
        }
        assert {tuple(row) for row in rows} == {
            ("OPERATIVA", "Inspección inicial aprobada"),
            ("FUERA_DE_SERVICIO", "Falla crítica detectada"),
            ("OPERATIVA", "Reparación verificada en reinspección"),
        }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_complete_persisted_journey_closes_finding_and_generates_pdf(
    migrated_database: str,
    app_database_url: str,
) -> None:
    del migrated_database
    engine = create_async_engine(app_database_url)

    async def run_as(actor_key: str, action):
        async with AsyncSession(engine) as session:
            async with session.begin():
                await apply_authorization_context(
                    session,
                    AuthorizationContext(
                        organization_id=PILOT_ORGANIZATION_ID,
                        actor_id=PILOT_ACTORS[actor_key].id,
                    ),
                )
                return await action(
                    PilotService(
                        PilotRequestContext(actor=PILOT_ACTORS[actor_key], session=session)
                    )
                )

    try:
        worksite = await run_as(
            "tecnico",
            lambda service: service.create_worksite(
                WorksiteCreate(
                    code="SYN-COMPLETE-JOURNEY",
                    name="Obra recorrido completo",
                    jurisdiction="Provincia sintética",
                )
            ),
        )
        await run_as(
            "tecnico",
            lambda service: service.create_document(
                worksite.id,
                DocumentCreate(
                    subject_kind=SubjectKind.WORKSITE,
                    subject_id=worksite.id,
                    title="Documento de recorrido",
                    document_type="SEGURO",
                    review_status="APROBADO",
                    valid_from=date(2026, 9, 1),
                    expires_on=date(2099, 12, 31),
                ),
            ),
        )
        audit = await run_as("auditor", lambda service: service.start_audit(worksite.id))
        await run_as(
            "auditor",
            lambda service: service.create_audit_control(
                audit.id,
                AuditControlCreate(
                    catalog_code="SYN-CIRCULACION-001",
                    result=ControlResult.CUMPLE,
                ),
            ),
        )
        finding_response = await run_as(
            "auditor",
            lambda service: service.create_audit_control(
                audit.id,
                AuditControlCreate(
                    catalog_code="SYN-EPP-001",
                    result=ControlResult.NO_CUMPLE,
                    severity_code="MEDIA",
                    finding_description="Completar la entrega sintética de EPP.",
                ),
            ),
        )
        await run_as(
            "auditor",
            lambda service: service.create_audit_control(
                audit.id,
                AuditControlCreate(
                    catalog_code="SYN-ORDEN-001",
                    result=ControlResult.NO_APLICA,
                    reason="No aplica al caso sintético.",
                ),
            ),
        )
        assert finding_response.finding is not None
        finding_id = finding_response.finding.id
        finalized = await run_as("auditor", lambda service: service.finalize_audit(audit.id))
        assert finalized.status.value == "FINALIZADA"

        await run_as(
            "tecnico",
            lambda service: service.create_correction(
                finding_id,
                CorrectionCreate(
                    description="Se completó la entrega sintética.",
                    evidence_note="Registro textual de verificación de entrega.",
                ),
            ),
        )
        await run_as("tecnico", lambda service: service.submit_verification(finding_id))
        closed = await run_as(
            "responsable-suplente",
            lambda service: service.verify_finding(
                finding_id,
                VerificationCreate(
                    decision=VerificationDecision.ACEPTADA,
                    notes="Corrección sintética verificada por un actor independiente.",
                ),
            ),
        )
        detail = await run_as(
            "responsable-suplente",
            lambda service: service.get_worksite_detail(worksite.id),
        )
        pdf = build_worksite_report_pdf(detail)
    finally:
        await engine.dispose()

    assert closed.status.value == "CERRADO"
    assert detail.metrics.findings.by_status["CERRADO"] == 1
    assert detail.metrics.documents.by_status["VIGENTE"] == 1
    assert detail.metrics.controls.numerator == 1
    assert detail.metrics.controls.denominator == 2
    assert detail.metrics.controls.excluded.no_aplica == 1
    assert pdf.startswith(b"%PDF-1.4")
    assert b"SYN-COMPLETE-JOURNEY" in pdf
    assert b"CERRADO" in pdf
    assert pdf.endswith(b"%%EOF\n")
