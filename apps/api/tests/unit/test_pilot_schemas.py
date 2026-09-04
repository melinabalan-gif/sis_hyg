from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from hys_api.modules.pilot.schemas import (
    AuditControlCreate,
    AuditControlView,
    AuditStartCreate,
    AuditView,
    ControlResult,
    DocumentDisplayStatus,
    DocumentReviewStatus,
    DocumentVersionCreate,
    DocumentView,
    FindingView,
    MachineInspectionCreate,
    MachineView,
    WorksiteCreate,
    WorksiteFunctionalAssignmentCreate,
    WorksiteStageCreate,
    derive_document_status,
    derive_worksite_metrics,
)


@pytest.mark.parametrize(
    ("review_status", "expires_on", "expected"),
    [
        ("PENDIENTE", None, DocumentDisplayStatus.PENDIENTE),
        ("RECHAZADO", None, DocumentDisplayStatus.RECHAZADO),
        ("APROBADO", None, DocumentDisplayStatus.FALTANTE),
        ("APROBADO", date(2026, 8, 31), DocumentDisplayStatus.VENCIDO),
        ("APROBADO", date(2026, 9, 1), DocumentDisplayStatus.POR_VENCER),
        ("APROBADO", date(2026, 10, 1), DocumentDisplayStatus.POR_VENCER),
        ("APROBADO", date(2026, 10, 2), DocumentDisplayStatus.VIGENTE),
    ],
)
def test_document_status_is_derived_at_argentina_date_boundaries(
    review_status: DocumentReviewStatus | str,
    expires_on: date | None,
    expected: DocumentDisplayStatus,
) -> None:
    assert (
        derive_document_status(
            review_status,
            expires_on,
            today=date(2026, 9, 1),
        )
        is expected
    )


@pytest.mark.parametrize("result", ["NO_APLICA", "NO_VERIFICADO"])
def test_unresolved_control_results_require_reason(result: str) -> None:
    with pytest.raises(ValidationError, match="reason es obligatorio"):
        AuditControlCreate.model_validate(
            {
                "catalog_code": "SYN-ORDEN-001",
                "result": result,
            }
        )


def test_non_compliant_control_requires_finding_data() -> None:
    with pytest.raises(ValidationError, match="severity_code y finding_description"):
        AuditControlCreate(
            catalog_code="SYN-ORDEN-001",
            result=ControlResult.NO_CUMPLE,
        )


def test_non_compliant_control_accepts_complete_finding_data() -> None:
    payload = AuditControlCreate(
        catalog_code="SYN-ORDEN-001",
        result=ControlResult.NO_CUMPLE,
        severity_code="ALTA",
        finding_description="Desvío sintético para prueba.",
    )

    assert payload.severity_code == "ALTA"


def test_audit_view_keeps_catalog_controls_separate_from_responses() -> None:
    actor_id = uuid4()
    audit = AuditView(
        id=uuid4(),
        status="EN_CURSO",
        author_id=actor_id,
        editor_id=actor_id,
        started_at="2026-09-03T15:00:00Z",
        finalized_at=None,
        available_controls=[
            {
                "catalog_code": "SYN-ORDEN-001",
                "catalog_title": "Orden sintético",
            },
            {
                "catalog_code": "SYN-EPP-001",
                "catalog_title": "EPP sintético",
            },
        ],
        controls=[],
    )

    assert [item.catalog_code for item in audit.available_controls] == [
        "SYN-ORDEN-001",
        "SYN-EPP-001",
    ]
    assert audit.controls == []


def test_strict_schemas_reject_server_or_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorksiteCreate.model_validate(
            {
                "code": "SYN-OBRA-001",
                "name": "Obra Sintética Uno",
                "organization_id": "00000000-0000-4000-8000-000000000001",
            }
        )


def test_expiry_window_is_exactly_thirty_days() -> None:
    today = date(2026, 9, 1)
    assert (
        derive_document_status("APROBADO", today + timedelta(days=30), today=today)
        is DocumentDisplayStatus.POR_VENCER
    )
    assert (
        derive_document_status("APROBADO", today + timedelta(days=31), today=today)
        is DocumentDisplayStatus.VIGENTE
    )


def test_worksite_creation_requires_jurisdiction() -> None:
    with pytest.raises(ValidationError, match="jurisdiction"):
        WorksiteCreate(code="SYN-OBRA-001", name="Obra Sintética Uno")


def test_worksite_stages_allow_simultaneous_intervals() -> None:
    first = WorksiteStageCreate(
        code="STG-001",
        name="Preparación",
        started_on=date(2026, 9, 1),
        ended_on=date(2026, 9, 30),
    )
    second = WorksiteStageCreate(
        code="STG-002",
        name="Montaje",
        started_on=date(2026, 9, 15),
    )

    assert first.started_on < second.started_on < first.ended_on


def test_worksite_stage_rejects_inverted_interval() -> None:
    with pytest.raises(ValidationError, match="ended_on debe ser posterior"):
        WorksiteStageCreate(
            code="STG-001",
            name="Preparación",
            started_on=date(2026, 9, 30),
            ended_on=date(2026, 9, 1),
        )


def test_functional_assignment_keeps_function_and_profession_separate() -> None:
    assignment = WorksiteFunctionalAssignmentCreate(
        actor_id=uuid4(),
        function_code="AUDITOR_DELEGADO_PROYECTO",
        permission_scope="WORKSITE",
        valid_from=date(2026, 9, 1),
    )
    assert assignment.function_code.value == "AUDITOR_DELEGADO_PROYECTO"
    assert AuditStartCreate(auditor_assignment_id=assignment.actor_id).auditor_assignment_id


def test_functional_assignment_rejects_inverted_validity() -> None:
    with pytest.raises(ValidationError, match="valid_to debe ser posterior"):
        WorksiteFunctionalAssignmentCreate(
            actor_id=uuid4(),
            function_code="TECNICO_HYS_CONTRATISTA_PRINCIPAL",
            valid_from=date(2026, 9, 30),
            valid_to=date(2026, 9, 1),
        )


def test_document_version_rejects_inverted_interval() -> None:
    with pytest.raises(ValidationError, match="expires_on no puede ser anterior"):
        DocumentVersionCreate(
            title="Seguro actualizado",
            document_type="SEGURO",
            valid_from=date(2026, 9, 30),
            expires_on=date(2026, 9, 1),
        )


def test_machine_inspection_requires_a_non_blank_reason() -> None:
    with pytest.raises(ValidationError, match="reason"):
        MachineInspectionCreate(resulting_status="CON_OBSERVACIONES", reason=" ")


def test_worksite_metrics_reconcile_visible_records() -> None:
    now = datetime(2026, 9, 4, 15, 0, tzinfo=UTC)
    worksite_id = uuid4()
    audit_id = uuid4()
    metrics = derive_worksite_metrics(
        [
            DocumentView(
                id=uuid4(),
                subject_kind="WORKSITE",
                subject_id=worksite_id,
                subject_name="Obra sintética",
                version=1,
                title="Documento vigente",
                document_type="SEGURO",
                review_status="APROBADO",
                status="VIGENTE",
                valid_from=None,
                expires_on=date(2026, 12, 31),
                notes=None,
                created_at=now,
            ),
            DocumentView(
                id=uuid4(),
                subject_kind="WORKSITE",
                subject_id=worksite_id,
                subject_name="Obra sintética",
                version=1,
                title="Documento pendiente",
                document_type="EPP",
                review_status="PENDIENTE",
                status="PENDIENTE",
                valid_from=None,
                expires_on=None,
                notes=None,
                created_at=now,
            ),
        ],
        [
            FindingView(
                id=uuid4(),
                audit_id=audit_id,
                audit_control_id=uuid4(),
                title="Desvío abierto",
                description="Desvío sintético",
                severity_code="ALTA",
                status="ABIERTO",
                due_at=datetime(2026, 9, 3, 15, 0, tzinfo=UTC),
                overdue=True,
                closed_at=None,
                created_by=uuid4(),
            ),
            FindingView(
                id=uuid4(),
                audit_id=audit_id,
                audit_control_id=uuid4(),
                title="Desvío cerrado",
                description="Desvío sintético cerrado",
                severity_code="BAJA",
                status="CERRADO",
                due_at=datetime(2026, 9, 3, 15, 0, tzinfo=UTC),
                overdue=False,
                closed_at=now,
                created_by=uuid4(),
            ),
        ],
        [
            MachineView(
                id=uuid4(),
                assignment_id=uuid4(),
                internal_code="MAQ-001",
                description="Equipo sintético",
                status="OPERATIVA",
                version=1,
                contractor_id=None,
                inspection_reason="Inspección sintética",
                inspected_at=now,
                started_on=now.date(),
                ended_on=None,
                inspections=[],
            ),
            MachineView(
                id=uuid4(),
                assignment_id=uuid4(),
                internal_code="MAQ-002",
                description="Equipo sintético fuera de servicio",
                status="FUERA_DE_SERVICIO",
                version=1,
                contractor_id=None,
                inspection_reason="Falla sintética",
                inspected_at=now,
                started_on=now.date(),
                ended_on=None,
                inspections=[],
            ),
        ],
        [
            AuditView(
                id=audit_id,
                status="FINALIZADA",
                author_id=uuid4(),
                editor_id=uuid4(),
                started_at=now,
                finalized_at=now,
                available_controls=[],
                controls=[
                    AuditControlView(
                        id=uuid4(),
                        catalog_code="SYN-001",
                        catalog_title="Control sintético",
                        result="CUMPLE",
                        reason=None,
                        finding_id=None,
                    ),
                    AuditControlView(
                        id=uuid4(),
                        catalog_code="SYN-002",
                        catalog_title="Control sintético",
                        result="NO_CUMPLE",
                        reason="Desvío sintético",
                        finding_id=uuid4(),
                    ),
                    AuditControlView(
                        id=uuid4(),
                        catalog_code="SYN-003",
                        catalog_title="Control sintético",
                        result="NO_APLICA",
                        reason="No corresponde en esta etapa",
                        finding_id=None,
                    ),
                ],
            )
        ],
        now=now,
    )

    assert metrics.documents.total == 2
    assert metrics.documents.by_status == {
        DocumentDisplayStatus.FALTANTE: 0,
        DocumentDisplayStatus.PENDIENTE: 1,
        DocumentDisplayStatus.RECHAZADO: 0,
        DocumentDisplayStatus.POR_VENCER: 0,
        DocumentDisplayStatus.VENCIDO: 0,
        DocumentDisplayStatus.VIGENTE: 1,
    }
    assert metrics.findings.total == 2
    assert metrics.findings.by_status["ABIERTO"] == 1
    assert metrics.findings.by_status["CERRADO"] == 1
    assert metrics.findings.overdue == 1
    assert metrics.machines.by_status["OPERATIVA"] == 1
    assert metrics.machines.by_status["FUERA_DE_SERVICIO"] == 1
    assert metrics.latest_audit is not None
    assert metrics.latest_audit.id == audit_id
    assert metrics.controls.audit_id == audit_id
    assert metrics.controls.numerator == 1
    assert metrics.controls.denominator == 2
    assert metrics.controls.ratio == 0.5
    assert metrics.controls.excluded.no_aplica == 1
    assert metrics.controls.excluded.no_verificado == 0


def test_worksite_metrics_have_explicit_empty_state() -> None:
    now = datetime(2026, 9, 4, 15, 0, tzinfo=UTC)

    metrics = derive_worksite_metrics([], [], [], [], now=now)

    assert metrics.documents.total == 0
    assert all(value == 0 for value in metrics.documents.by_status.values())
    assert metrics.findings.total == 0
    assert all(value == 0 for value in metrics.findings.by_status.values())
    assert metrics.findings.overdue == 0
    assert metrics.machines.total == 0
    assert all(value == 0 for value in metrics.machines.by_status.values())
    assert metrics.latest_audit is None
    assert metrics.controls.numerator == 0
    assert metrics.controls.denominator == 0
    assert metrics.controls.ratio is None


def test_control_ratio_excludes_only_no_aplica_and_no_verificado() -> None:
    now = datetime(2026, 9, 4, 15, 0, tzinfo=UTC)
    audit = AuditView(
        id=uuid4(),
        status="EN_CURSO",
        author_id=uuid4(),
        editor_id=uuid4(),
        started_at=now,
        finalized_at=None,
        available_controls=[],
        controls=[
            AuditControlView(
                id=uuid4(),
                catalog_code="SYN-001",
                catalog_title="Control sintético",
                result="NO_APLICA",
                reason="No corresponde",
                finding_id=None,
            ),
            AuditControlView(
                id=uuid4(),
                catalog_code="SYN-002",
                catalog_title="Control sintético",
                result="NO_VERIFICADO",
                reason="Sin evidencia en la demo",
                finding_id=None,
            ),
        ],
    )

    metrics = derive_worksite_metrics([], [], [], [audit], now=now)

    assert metrics.controls.numerator == 0
    assert metrics.controls.denominator == 0
    assert metrics.controls.ratio is None
    assert metrics.controls.excluded.no_aplica == 1
    assert metrics.controls.excluded.no_verificado == 1
