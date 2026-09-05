from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI

from hys_api.api.dependencies import PilotActor, get_pilot_actor
from hys_api.modules.pilot.schemas import (
    DocumentVersionCreate,
    DocumentView,
    MachineInspectionCreate,
    MachineInspectionView,
    MachineView,
    WorksiteDetail,
    WorksiteMetrics,
    WorksiteStageCreate,
    WorksiteStageView,
    WorksiteSummary,
)
from hys_api.modules.pilot.service import get_pilot_service

WORKSITE_ID = UUID("00000000-0000-4000-8000-000000000501")
NOW = datetime(2026, 9, 3, 15, 0, tzinfo=UTC)


class FakePilotService:
    def __init__(self, actor: PilotActor) -> None:
        self.actor = actor

    async def list_worksites(self) -> list[WorksiteSummary]:
        return [self._summary()]

    async def get_worksite_detail(self, _worksite_id: UUID) -> WorksiteDetail:
        return WorksiteDetail(
            **self._summary().model_dump(),
            contractors=[],
            people=[],
            documents=[],
            machines=[],
            audits=[],
            findings=[],
            stages=[],
            metrics=WorksiteMetrics(
                documents={
                    "total": 0,
                    "by_status": {
                        "FALTANTE": 0,
                        "PENDIENTE": 0,
                        "OBSERVADO": 0,
                        "RECHAZADO": 0,
                        "POR_VENCER": 0,
                        "VENCIDO": 0,
                        "VIGENTE": 0,
                    },
                },
                findings={
                    "total": 0,
                    "by_status": {
                        "ABIERTO": 0,
                        "EN_CORRECCION": 0,
                        "PENDIENTE_VERIFICACION": 0,
                        "CERRADO": 0,
                    },
                    "overdue": 0,
                },
                machines={
                    "total": 0,
                    "by_status": {
                        "OPERATIVA": 0,
                        "CON_OBSERVACIONES": 0,
                        "FUERA_DE_SERVICIO": 0,
                    },
                },
                latest_audit=None,
                controls={
                    "audit_id": None,
                    "numerator": 0,
                    "denominator": 0,
                    "ratio": None,
                    "excluded": {"no_aplica": 0, "no_verificado": 0},
                },
                calculated_at=NOW,
            ),
        )

    async def create_worksite_stage(
        self, _worksite_id: UUID, payload: WorksiteStageCreate
    ) -> WorksiteStageView:
        return WorksiteStageView(
            id=UUID("00000000-0000-4000-8000-000000000601"),
            worksite_id=WORKSITE_ID,
            code=payload.code,
            name=payload.name,
            started_on=payload.started_on,
            ended_on=payload.ended_on,
            sector=payload.sector,
            notes=payload.notes,
            created_at=NOW,
            updated_at=NOW,
        )

    async def create_document_version(
        self,
        _worksite_id: UUID,
        _document_id: UUID,
        payload: DocumentVersionCreate,
    ) -> DocumentView:
        return DocumentView(
            id=UUID("00000000-0000-4000-8000-000000000701"),
            subject_kind="WORKSITE",
            subject_id=WORKSITE_ID,
            subject_name="Obra Sintética Uno",
            version=2,
            title=payload.title,
            document_type=payload.document_type,
            review_status=payload.review_status,
            status="VIGENTE",
            valid_from=payload.valid_from,
            expires_on=payload.expires_on,
            notes=payload.notes,
            created_at=NOW,
            versions=[],
        )

    async def create_machine_inspection(
        self,
        _worksite_id: UUID,
        machine_id: UUID,
        payload: MachineInspectionCreate,
    ) -> MachineView:
        inspection = MachineInspectionView(
            id=UUID("00000000-0000-4000-8000-000000000801"),
            resulting_status=payload.resulting_status,
            reason=payload.reason,
            actor_id=self.actor.id,
            inspected_at=NOW,
        )
        return MachineView(
            id=machine_id,
            assignment_id=UUID("00000000-0000-4000-8000-000000000802"),
            internal_code="MAQ-001",
            description="Autoelevador sintético",
            status=payload.resulting_status,
            version=2,
            contractor_id=None,
            inspection_reason=payload.reason,
            inspected_at=NOW,
            started_on=NOW.date(),
            ended_on=None,
            inspections=[inspection],
        )

    @staticmethod
    def _summary() -> WorksiteSummary:
        return WorksiteSummary(
            id=WORKSITE_ID,
            code="SYN-OBRA-001",
            name="Obra Sintética Uno",
            jurisdiction="Provincia sintética",
            status="ACTIVE",
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )


async def fake_pilot_service(
    actor: Annotated[PilotActor, Depends(get_pilot_actor)],
) -> FakePilotService:
    return FakePilotService(actor)


@pytest.fixture
def pilot_app(app: FastAPI) -> FastAPI:
    app.dependency_overrides[get_pilot_service] = fake_pilot_service
    return app


@pytest.mark.asyncio
async def test_pilot_routes_require_synthetic_actor(client, pilot_app: FastAPI) -> None:
    del pilot_app
    response = await client.get("/api/v1/worksites")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "pilot_authentication_required"


@pytest.mark.asyncio
async def test_worksite_list_is_a_direct_summary_array(client, pilot_app: FastAPI) -> None:
    del pilot_app
    response = await client.get(
        "/api/v1/worksites",
        headers={"X-Pilot-Actor": "auditor"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(WORKSITE_ID),
            "code": "SYN-OBRA-001",
            "name": "Obra Sintética Uno",
            "status": "ACTIVE",
            "version": 1,
            "created_at": "2026-09-03T15:00:00Z",
            "updated_at": "2026-09-03T15:00:00Z",
                "jurisdiction": "Provincia sintética",
                "country": None,
                "province": None,
                "municipality": None,
        }
    ]


@pytest.mark.asyncio
async def test_worksite_detail_has_direct_aggregate_arrays(client, pilot_app: FastAPI) -> None:
    del pilot_app
    response = await client.get(
        f"/api/v1/worksites/{WORKSITE_ID}",
        headers={"X-Pilot-Actor": "tecnico"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {
        "id",
        "code",
        "name",
        "status",
        "version",
        "created_at",
        "updated_at",
            "jurisdiction",
            "country",
            "province",
            "municipality",
        "contractors",
        "functional_assignments",
        "people",
        "documents",
        "machines",
        "audits",
        "findings",
        "stages",
        "metrics",
    }
    assert response.json()["contractors"] == []
    assert response.json()["findings"] == []


@pytest.mark.asyncio
async def test_worksite_stage_route_serializes_temporal_fields(client, pilot_app: FastAPI) -> None:
    del pilot_app
    response = await client.post(
        f"/api/v1/worksites/{WORKSITE_ID}/stages",
        headers={"X-Pilot-Actor": "tecnico"},
        json={
            "code": "STG-001",
            "name": "Preparación",
            "started_on": "2026-09-01",
            "ended_on": "2026-09-15",
            "sector": "Norte",
            "notes": "Etapa sintética",
        },
    )

    assert response.status_code == 201
    assert response.json()["code"] == "STG-001"
    assert response.json()["started_on"] == "2026-09-01"


@pytest.mark.asyncio
async def test_worksite_stage_route_returns_problem_details_for_inverted_interval(
    client, pilot_app: FastAPI
) -> None:
    del pilot_app
    response = await client.post(
        f"/api/v1/worksites/{WORKSITE_ID}/stages",
        headers={"X-Pilot-Actor": "tecnico"},
        json={
            "code": "STG-001",
            "name": "Preparación",
            "started_on": "2026-09-15",
            "ended_on": "2026-09-01",
        },
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"
    assert "ended_on debe ser posterior" in response.json()["errors"][0]["message"]


@pytest.mark.asyncio
async def test_document_version_route_preserves_worksite_subject_and_serializes_version(
    client, pilot_app: FastAPI
) -> None:
    del pilot_app
    response = await client.post(
        f"/api/v1/worksites/{WORKSITE_ID}/documents/00000000-0000-4000-8000-000000000501/versions",
        headers={"X-Pilot-Actor": "tecnico"},
        json={
            "title": "Seguro actualizado",
            "document_type": "SEGURO",
            "review_status": "APROBADO",
            "valid_from": "2026-09-03",
            "expires_on": "2027-09-03",
            "notes": "Metadata sintética",
        },
    )

    assert response.status_code == 201
    assert response.json()["version"] == 2
    assert response.json()["subject_id"] == str(WORKSITE_ID)


@pytest.mark.asyncio
async def test_document_version_route_returns_problem_details_for_invalid_dates(
    client, pilot_app: FastAPI
) -> None:
    del pilot_app
    response = await client.post(
        f"/api/v1/worksites/{WORKSITE_ID}/documents/00000000-0000-4000-8000-000000000501/versions",
        headers={"X-Pilot-Actor": "tecnico"},
        json={
            "title": "Seguro inválido",
            "document_type": "SEGURO",
            "valid_from": "2026-09-15",
            "expires_on": "2026-09-01",
        },
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"
    assert "expires_on no puede ser anterior" in response.json()["errors"][0]["message"]


@pytest.mark.asyncio
async def test_machine_inspection_route_serializes_transition_and_history(
    client, pilot_app: FastAPI
) -> None:
    del pilot_app
    machine_id = UUID("00000000-0000-4000-8000-000000000803")
    response = await client.post(
        f"/api/v1/worksites/{WORKSITE_ID}/machines/{machine_id}/inspections",
        headers={"X-Pilot-Actor": "tecnico"},
        json={
            "resulting_status": "CON_OBSERVACIONES",
            "reason": "Observación sintética",
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
                "specific_devices": "CUMPLE",
            },
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "CON_OBSERVACIONES"
    assert response.json()["version"] == 2
    assert response.json()["inspections"][0]["actor_id"] == str(
        UUID("00000000-0000-4000-8000-000000000002")
    )


@pytest.mark.asyncio
async def test_machine_inspection_route_rejects_blank_reason(client, pilot_app: FastAPI) -> None:
    del pilot_app
    response = await client.post(
        f"/api/v1/worksites/{WORKSITE_ID}/machines/{uuid4()}/inspections",
        headers={"X-Pilot-Actor": "tecnico"},
        json={
            "resulting_status": "OPERATIVA",
            "reason": " ",
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
                "specific_devices": "CUMPLE",
            },
        },
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"
    assert response.json()["errors"][0]["location"] == ["body", "reason"]


@pytest.mark.asyncio
async def test_worksite_report_route_returns_a_pdf_attachment(client, pilot_app: FastAPI) -> None:
    del pilot_app
    response = await client.get(
        f"/api/v1/worksites/{WORKSITE_ID}/report.pdf",
        headers={"X-Pilot-Actor": "responsable"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    disposition = response.headers["content-disposition"]
    assert disposition == 'attachment; filename="syn-obra-001-reporte.pdf"'
    assert response.content.startswith(b"%PDF-1.4")
    assert response.content.endswith(b"%%EOF\n")
