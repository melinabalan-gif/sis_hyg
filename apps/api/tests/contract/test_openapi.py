import json
from pathlib import Path

from fastapi import FastAPI


def test_openapi_exposes_the_versioned_public_contract(app: FastAPI) -> None:
    schema = app.openapi()

    assert set(schema["paths"]) == {
        "/api/v1/audits/{audit_id}/controls",
        "/api/v1/audits/{audit_id}/finalize",
        "/api/v1/audits/{audit_id}",
        "/api/v1/audits/{audit_id}/report.pdf",
        "/api/v1/audits/{audit_id}/unregistered-people",
        "/api/v1/findings/{finding_id}/corrections",
        "/api/v1/findings/{finding_id}/submit-verification",
        "/api/v1/findings/{finding_id}/timeline",
        "/api/v1/findings/{finding_id}/verifications",
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/worksites",
        "/api/v1/worksites/{worksite_id}",
        "/api/v1/worksites/{worksite_id}/report.pdf",
        "/api/v1/worksites/{worksite_id}/audits",
        "/api/v1/worksites/{worksite_id}/contractors",
        "/api/v1/worksites/{worksite_id}/documents",
        "/api/v1/worksites/{worksite_id}/documents/{document_id}/versions",
        "/api/v1/worksites/{worksite_id}/functional-assignments",
        "/api/v1/worksites/{worksite_id}/machines",
        "/api/v1/worksites/{worksite_id}/machines/{machine_id}/inspections",
        "/api/v1/worksites/{worksite_id}/people",
        "/api/v1/worksites/{worksite_id}/people/{person_id}/verifications",
        "/api/v1/worksites/{worksite_id}/stages",
        "/api/v1/worksites/{worksite_id}/stages/{stage_id}",
        "/api/v1/worksites/{worksite_id}/documents/{document_id}/reviews",
        "/api/v1/worksites/{worksite_id}/machines/{machine_id}/inspections/{inspection_id}/validations",
    }
    ready_responses = schema["paths"]["/api/v1/health/ready"]["get"]["responses"]
    assert set(ready_responses["503"]["content"]) == {"application/problem+json"}
    assert set(ready_responses["422"]["content"]) == {"application/problem+json"}
    assert schema["info"]["version"] == "0.1.0"
    assert "sintéticos" in schema["info"]["description"]
    audit_view = schema["components"]["schemas"]["AuditView"]
    assert "available_controls" in audit_view["properties"]
    assert "AuditCatalogControlView" in json.dumps(audit_view["properties"])
    machine_view = schema["components"]["schemas"]["MachineView"]
    assert {"version", "inspections"} <= set(machine_view["properties"])
    assert "MachineInspectionView" in json.dumps(machine_view["properties"])
    assert "DocumentReviewView" in json.dumps(
        schema["components"]["schemas"]["DocumentView"]["properties"]
    )


def test_openapi_matches_versioned_snapshot(app: FastAPI) -> None:
    api_root = Path(__file__).resolve().parents[2]
    snapshot = json.loads((api_root / "openapi.json").read_text(encoding="utf-8"))

    assert app.openapi() == snapshot


def test_openapi_does_not_contain_dangling_local_definitions(app: FastAPI) -> None:
    serialized = json.dumps(app.openapi())

    assert '"$ref": "#/$defs/' not in serialized
