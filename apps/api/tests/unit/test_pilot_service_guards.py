from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hys_api.api.dependencies import PILOT_ACTORS, PILOT_ORGANIZATION_ID, PilotRequestContext
from hys_api.core.errors import ProblemException
from hys_api.modules.pilot.models import (
    Audit,
    ControlCatalogVersion,
    Correction,
    Document,
    DocumentVersion,
    Finding,
    Machine,
    MachineInspection,
    MachineWorksiteAssignment,
    WorksiteFunctionalAssignment,
)
from hys_api.modules.pilot.schemas import (
    AuditControlCreate,
    ControlResult,
    DocumentVersionCreate,
    MachineInspectionCreate,
    VerificationCreate,
    VerificationDecision,
    WorksiteStageCreate,
)
from hys_api.modules.pilot.service import PilotService
from hys_api.modules.worksites.models import Worksite


def _service(actor_key: str) -> tuple[PilotService, MagicMock]:
    session = MagicMock(spec=AsyncSession)
    session.scalar = AsyncMock()
    session.flush = AsyncMock()
    context = PilotRequestContext(actor=PILOT_ACTORS[actor_key], session=session)
    return PilotService(context), session


def _checklist() -> dict[str, str]:
    return {
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
    }


def test_legacy_compatibility_selector_maps_to_contractor_responsible_function() -> None:
    service, session = _service("tecnico")
    service._add_compatibility_assignments(uuid4())

    assignments = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], WorksiteFunctionalAssignment)
    ]
    suplente = next(
        assignment
        for assignment in assignments
        if assignment.actor_id == PILOT_ACTORS["responsable-suplente"].id
    )

    assert suplente.function_code == "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL"


def _audit(*, editor_id: UUID, status: str) -> Audit:
    now = datetime.now(UTC)
    return Audit(
        id=uuid4(),
        organization_id=PILOT_ORGANIZATION_ID,
        worksite_id=uuid4(),
        status=status,
        author_actor_id=editor_id,
        editor_actor_id=editor_id,
        started_at=now,
        finalized_at=now if status == "FINALIZADA" else None,
        created_at=now,
        updated_at=now,
        version=1,
        control_catalog_version_id=uuid4(),
    )


def _catalog_controls() -> list[ControlCatalogVersion]:
    published_at = datetime(2026, 9, 3, tzinfo=UTC)
    return [
        ControlCatalogVersion(
            id=UUID(f"00000000-0000-4000-8000-00000000010{index}"),
            organization_id=PILOT_ORGANIZATION_ID,
            code=code,
            title=title,
            version_number=1,
            published_at=published_at,
        )
        for index, (code, title) in enumerate(
            [
                ("SYN-CIRCULACION-001", "Circulación sintética"),
                ("SYN-EPP-001", "EPP sintético"),
                ("SYN-ORDEN-001", "Orden sintético"),
            ],
            start=2,
        )
    ]


def _configure_catalog_session(
    session: MagicMock,
    audit: Audit,
    *,
    answered_codes: list[str] | None = None,
) -> list[ControlCatalogVersion]:
    catalog_controls = _catalog_controls()
    session.scalar.side_effect = [audit, catalog_controls[-1], None]
    session.scalars.side_effect = [
        catalog_controls,
        answered_codes or [],
    ]
    session.execute.return_value = MagicMock()
    session.execute.return_value.all.return_value = []
    session.refresh = AsyncMock(side_effect=lambda instance: setattr(instance, "id", uuid4()))
    return catalog_controls


@pytest.mark.asyncio
async def test_finalized_audit_rejects_new_controls() -> None:
    service, session = _service("auditor")
    audit = _audit(editor_id=PILOT_ACTORS["auditor"].id, status="FINALIZADA")
    session.scalar.return_value = audit

    with pytest.raises(ProblemException) as raised:
        await service.create_audit_control(
            audit.id,
            AuditControlCreate(
                catalog_code="SYN-ORDEN-001",
                result=ControlResult.CUMPLE,
            ),
        )

    assert raised.value.status == 409
    assert raised.value.code == "audit_already_finalized"


@pytest.mark.asyncio
async def test_non_editor_cannot_finalize_audit() -> None:
    service, session = _service("responsable")
    audit = _audit(editor_id=PILOT_ACTORS["auditor"].id, status="EN_CURSO")
    session.scalar.return_value = audit

    with pytest.raises(ProblemException) as raised:
        await service.finalize_audit(audit.id)

    assert raised.value.status == 403
    assert raised.value.code == "audit_editor_required"


@pytest.mark.asyncio
async def test_audit_accepts_every_control_in_its_catalog_snapshot() -> None:
    service, session = _service("auditor")
    audit = _audit(editor_id=PILOT_ACTORS["auditor"].id, status="EN_CURSO")
    catalog_controls = _configure_catalog_session(session, audit)

    response = await service.create_audit_control(
        audit.id,
        AuditControlCreate(
            catalog_code="SYN-EPP-001",
            result=ControlResult.CUMPLE,
        ),
    )

    assert response.control.catalog_code == catalog_controls[1].code
    assert response.control.catalog_title == catalog_controls[1].title


@pytest.mark.asyncio
async def test_audit_rejects_control_outside_its_catalog_snapshot() -> None:
    service, session = _service("auditor")
    audit = _audit(editor_id=PILOT_ACTORS["auditor"].id, status="EN_CURSO")
    _configure_catalog_session(session, audit)

    with pytest.raises(ProblemException) as raised:
        await service.create_audit_control(
            audit.id,
            AuditControlCreate(
                catalog_code="SYN-OTHER-TENANT-001",
                result=ControlResult.CUMPLE,
            ),
        )

    assert raised.value.status == 422
    assert raised.value.code == "invalid_catalog_control"
    assert session.scalar.await_count == 2


@pytest.mark.asyncio
async def test_audit_rejects_duplicate_response_for_snapshot_control() -> None:
    service, session = _service("auditor")
    audit = _audit(editor_id=PILOT_ACTORS["auditor"].id, status="EN_CURSO")
    _configure_catalog_session(session, audit)
    session.scalar.side_effect = [audit, _catalog_controls()[-1], uuid4()]

    with pytest.raises(ProblemException) as raised:
        await service.create_audit_control(
            audit.id,
            AuditControlCreate(
                catalog_code="SYN-ORDEN-001",
                result=ControlResult.CUMPLE,
            ),
        )

    assert raised.value.status == 409
    assert raised.value.code == "duplicate_audit_control"


@pytest.mark.asyncio
async def test_audit_cannot_finalize_until_snapshot_is_complete() -> None:
    service, session = _service("auditor")
    audit = _audit(editor_id=PILOT_ACTORS["auditor"].id, status="EN_CURSO")
    _configure_catalog_session(session, audit, answered_codes=["SYN-ORDEN-001"])

    with pytest.raises(ProblemException) as raised:
        await service.finalize_audit(audit.id)

    assert raised.value.status == 409
    assert raised.value.code == "audit_controls_incomplete"
    assert "SYN-CIRCULACION-001" in raised.value.detail
    assert "SYN-EPP-001" in raised.value.detail
    assert audit.status == "EN_CURSO"


@pytest.mark.asyncio
async def test_complete_audit_exposes_snapshot_and_becomes_immutable() -> None:
    service, session = _service("auditor")
    audit = _audit(editor_id=PILOT_ACTORS["auditor"].id, status="EN_CURSO")
    catalog_controls = _catalog_controls()
    session.scalar.side_effect = [audit, catalog_controls[-1], catalog_controls[-1]]
    session.scalars.side_effect = [
        catalog_controls,
        [catalog.code for catalog in catalog_controls],
        catalog_controls,
    ]
    session.execute.return_value = MagicMock()
    session.execute.return_value.all.return_value = []
    session.refresh = AsyncMock(side_effect=lambda instance: setattr(instance, "id", uuid4()))

    response = await service.finalize_audit(audit.id)

    assert response.status.value == "FINALIZADA"
    assert [item.catalog_code for item in response.available_controls] == [
        "SYN-CIRCULACION-001",
        "SYN-EPP-001",
        "SYN-ORDEN-001",
    ]
    assert audit.finalized_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("same_as", ["correction_author"])
async def test_verification_enforces_segregation_of_duties(same_as: str) -> None:
    service, _session = _service("responsable")
    actor_id = PILOT_ACTORS["responsable"].id
    other_id = PILOT_ACTORS["tecnico"].id
    finding = Finding(
        id=uuid4(),
        organization_id=PILOT_ORGANIZATION_ID,
        worksite_id=uuid4(),
        audit_id=uuid4(),
        title="Control sintético",
        description="Desvío sintético",
        status="PENDIENTE_VERIFICACION",
        severity_catalog_version_id=uuid4(),
        severity_code="ALTA",
        severity_label="Alta sintética",
        due_at=datetime.now(UTC),
        created_by_actor_id=actor_id if same_as == "creator" else other_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        version=1,
    )
    correction = Correction(
        id=uuid4(),
        organization_id=PILOT_ORGANIZATION_ID,
        finding_id=finding.id,
        description="Corrección sintética",
        evidence_note="Evidencia sintética",
        authored_by_actor_id=actor_id if same_as == "correction_author" else other_id,
        created_at=datetime.now(UTC),
    )
    service._get_finding = AsyncMock(return_value=finding)  # type: ignore[method-assign]
    service._latest_correction = AsyncMock(return_value=correction)  # type: ignore[method-assign]

    with pytest.raises(ProblemException) as raised:
        await service.verify_finding(
            finding.id,
            VerificationCreate(
                decision=VerificationDecision.ACEPTADA,
                notes="Verificación sintética independiente.",
            ),
        )

    assert raised.value.status == 409
    assert raised.value.code == "segregation_of_duties"


@pytest.mark.asyncio
async def test_stage_creation_requires_worksite_write_permission() -> None:
    service, _session = _service("auditor")

    with pytest.raises(ProblemException) as raised:
        await service.create_worksite_stage(
            uuid4(),
            WorksiteStageCreate(
                code="STG-001",
                name="Preparación",
                started_on=datetime(2026, 9, 1, tzinfo=UTC).date(),
            ),
        )

    assert raised.value.status == 403
    assert raised.value.code == "pilot_permission_denied"


@pytest.mark.asyncio
async def test_stage_creation_rejects_archived_worksite() -> None:
    service, session = _service("tecnico")
    worksite = Worksite(
        id=uuid4(),
        organization_id=PILOT_ORGANIZATION_ID,
        code="SYN-OBRA-001",
        name="Obra sintética",
        jurisdiction="Provincia sintética",
        status="ARCHIVED",
    )
    session.scalar.return_value = worksite

    with pytest.raises(ProblemException) as raised:
        await service.create_worksite_stage(
            worksite.id,
            WorksiteStageCreate(
                code="STG-001",
                name="Preparación",
                started_on=datetime(2026, 9, 1, tzinfo=UTC).date(),
            ),
        )

    assert raised.value.status == 409
    assert raised.value.code == "worksite_archived"


@pytest.mark.asyncio
async def test_document_version_requires_resource_write_permission() -> None:
    service, _session = _service("auditor")

    with pytest.raises(ProblemException) as raised:
        await service.create_document_version(
            uuid4(),
            uuid4(),
            DocumentVersionCreate(title="Updated title", document_type="SEGURO"),
        )

    assert raised.value.status == 403
    assert raised.value.code == "pilot_permission_denied"


@pytest.mark.asyncio
async def test_document_version_updates_current_projection_and_keeps_sequence() -> None:
    service, session = _service("tecnico")
    now = datetime.now(UTC)
    worksite = Worksite(
        id=uuid4(),
        organization_id=PILOT_ORGANIZATION_ID,
        code="SYN-OBRA-001",
        name="Obra sintética",
        jurisdiction="Provincia sintética",
        status="ACTIVE",
        created_by_actor_id=PILOT_ACTORS["tecnico"].id,
    )
    document = Document(
        id=uuid4(),
        organization_id=PILOT_ORGANIZATION_ID,
        title="Seguro inicial",
        document_type="SEGURO",
        review_status="APROBADO",
        version=1,
        created_at=now,
        updated_at=now,
    )
    version_one = DocumentVersion(
        id=uuid4(),
        organization_id=PILOT_ORGANIZATION_ID,
        document_id=document.id,
        version_number=1,
        title=document.title,
        document_type=document.document_type,
        review_status=document.review_status,
        actor_id=PILOT_ACTORS["tecnico"].id,
        created_at=now,
    )
    version_two = DocumentVersion(
        id=uuid4(),
        organization_id=PILOT_ORGANIZATION_ID,
        document_id=document.id,
        version_number=2,
        title="Seguro actualizado",
        document_type="SEGURO",
        review_status="APROBADO",
        actor_id=PILOT_ACTORS["tecnico"].id,
        created_at=now,
    )
    session.scalar.side_effect = [worksite, document]
    session.refresh = AsyncMock()
    session.scalars.return_value = [version_two, version_one]
    service._document_subject_for_worksite = AsyncMock(  # type: ignore[method-assign]
        return_value=("WORKSITE", worksite.id, worksite.name)
    )

    response = await service.create_document_version(
        worksite.id,
        document.id,
        DocumentVersionCreate(
            title="Seguro actualizado",
            document_type="SEGURO",
            review_status="APROBADO",
        ),
    )

    assert document.version == 2
    assert document.title == "Seguro actualizado"
    assert response.version == 2
    assert [item.version_number for item in response.versions] == [2, 1]


def _machine_fixture(
    *, worksite_id: UUID, status: str = "OPERATIVA"
) -> tuple[Machine, MachineWorksiteAssignment, MachineInspection]:
    now = datetime.now(UTC)
    machine_id = uuid4()
    machine = Machine(
        id=machine_id,
        organization_id=PILOT_ORGANIZATION_ID,
        internal_code="MAQ-001",
        description="Autoelevador sintético",
        status=status,
        version=1,
        created_at=now,
        updated_at=now,
    )
    assignment = MachineWorksiteAssignment(
        id=uuid4(),
        organization_id=PILOT_ORGANIZATION_ID,
        worksite_id=worksite_id,
        machine_id=machine_id,
        started_on=now.date(),
    )
    inspection = MachineInspection(
        id=uuid4(),
        organization_id=PILOT_ORGANIZATION_ID,
        machine_id=machine_id,
        worksite_id=worksite_id,
        resulting_status=status,
        reason="Inspección inicial sintética",
        actor_id=PILOT_ACTORS["tecnico"].id,
        inspected_at=now,
    )
    return machine, assignment, inspection


@pytest.mark.asyncio
async def test_machine_inspection_requires_resource_write_permission() -> None:
    service, session = _service("auditor")

    with pytest.raises(ProblemException) as raised:
        await service.record_machine_inspection(
            uuid4(),
            uuid4(),
                MachineInspectionCreate(
                    resulting_status="CON_OBSERVACIONES",
                    reason="Observación sintética",
                    checklist=_checklist(),
            ),
        )

    assert raised.value.status == 403
    assert raised.value.code == "pilot_permission_denied"
    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_machine_inspection_rejects_archived_worksite() -> None:
    service, session = _service("tecnico")
    worksite = Worksite(
        id=uuid4(),
        organization_id=PILOT_ORGANIZATION_ID,
        code="SYN-OBRA-ARCHIVED",
        name="Obra sintética archivada",
        jurisdiction="Provincia sintética",
        status="ARCHIVED",
    )
    session.scalar.return_value = worksite

    with pytest.raises(ProblemException) as raised:
        await service.record_machine_inspection(
            worksite.id,
            uuid4(),
                MachineInspectionCreate(
                    resulting_status="OPERATIVA",
                    reason="Reinspección sintética",
                    checklist=_checklist(),
            ),
        )

    assert raised.value.status == 409
    assert raised.value.code == "worksite_archived"


@pytest.mark.asyncio
async def test_machine_inspection_hides_unassigned_machine() -> None:
    service, session = _service("tecnico")
    worksite = Worksite(
        id=uuid4(),
        organization_id=PILOT_ORGANIZATION_ID,
        code="SYN-OBRA-001",
        name="Obra sintética",
        jurisdiction="Provincia sintética",
        status="ACTIVE",
        created_by_actor_id=PILOT_ACTORS["tecnico"].id,
    )
    session.scalar.side_effect = [worksite, None]

    with pytest.raises(ProblemException) as raised:
        await service.record_machine_inspection(
            worksite.id,
            uuid4(),
                MachineInspectionCreate(
                    resulting_status="OPERATIVA",
                    reason="Reinspección sintética",
                    checklist=_checklist(),
            ),
        )

    assert raised.value.status == 404
    assert raised.value.code == "pilot_resource_not_found"
    assert "machine" not in raised.value.detail.lower()


@pytest.mark.asyncio
async def test_machine_inspection_locks_updates_version_and_keeps_history() -> None:
    service, session = _service("tecnico")
    worksite_id = uuid4()
    worksite = Worksite(
        id=worksite_id,
        organization_id=PILOT_ORGANIZATION_ID,
        code="SYN-OBRA-001",
        name="Obra sintética",
        jurisdiction="Provincia sintética",
        status="ACTIVE",
        created_by_actor_id=PILOT_ACTORS["tecnico"].id,
    )
    machine, assignment, initial = _machine_fixture(worksite_id=worksite_id)
    session.scalar.side_effect = [worksite, machine, assignment]

    def add(instance: object) -> None:
        if isinstance(instance, MachineInspection):
            instance.id = uuid4()

    async def refresh(instance: object) -> None:
        if isinstance(instance, MachineInspection):
            instance.inspected_at = datetime.now(UTC)

    session.add.side_effect = add
    session.scalars.side_effect = lambda _statement: [session.add.call_args.args[0], initial]
    session.refresh = AsyncMock(side_effect=refresh)

    response = await service.record_machine_inspection(
        worksite_id,
        machine.id,
            MachineInspectionCreate(
                resulting_status="FUERA_DE_SERVICIO",
                reason="Falla crítica sintética",
                checklist=_checklist(),
        ),
    )

    assert machine.status == "FUERA_DE_SERVICIO"
    assert machine.version == 2
    assert response.status.value == "FUERA_DE_SERVICIO"
    assert response.version == 2
    assert [item.resulting_status.value for item in response.inspections] == [
        "FUERA_DE_SERVICIO",
        "OPERATIVA",
    ]
    assert session.add.call_count == 1
    machine_query = session.scalar.await_args_list[1].args[0]
    assert machine_query._for_update_arg is not None
