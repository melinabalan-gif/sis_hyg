import json
from pathlib import Path

from fastapi import FastAPI


def test_openapi_exposes_only_the_initial_public_contract(app: FastAPI) -> None:
    schema = app.openapi()

    assert set(schema["paths"]) == {
        "/api/v1/health/live",
        "/api/v1/health/ready",
    }
    ready_responses = schema["paths"]["/api/v1/health/ready"]["get"]["responses"]
    assert set(ready_responses["503"]["content"]) == {"application/problem+json"}
    assert set(ready_responses["422"]["content"]) == {"application/problem+json"}
    assert schema["info"]["version"] == "0.1.0"
    assert "sintéticos" in schema["info"]["description"]


def test_openapi_matches_versioned_snapshot(app: FastAPI) -> None:
    api_root = Path(__file__).resolve().parents[2]
    snapshot = json.loads((api_root / "openapi.json").read_text(encoding="utf-8"))

    assert app.openapi() == snapshot


def test_openapi_does_not_contain_dangling_local_definitions(app: FastAPI) -> None:
    serialized = json.dumps(app.openapi())

    assert '"$ref": "#/$defs/' not in serialized
