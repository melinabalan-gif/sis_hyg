from uuid import UUID

import httpx
from fastapi import FastAPI, Query

from hys_api.core.errors import ProblemException
from hys_api.db.readiness import ReadinessState, check_database_readiness
from hys_api.db.schema import EXPECTED_SCHEMA_REVISION


async def test_live_does_not_consult_database(app: FastAPI, client: httpx.AsyncClient) -> None:
    async def database_must_not_be_called() -> ReadinessState:
        raise AssertionError("liveness consultó una dependencia")

    app.dependency_overrides[check_database_readiness] = database_must_not_be_called
    request_id = "00000000-0000-0000-0000-000000000099"

    response = await client.get("/api/v1/health/live", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
    assert response.json() == {"status": "ok", "service": "hys-api", "version": "0.1.0"}


async def test_ready_returns_schema_revision(app: FastAPI, client: httpx.AsyncClient) -> None:
    async def database_is_ready() -> ReadinessState:
        return ReadinessState(schema_revision=EXPECTED_SCHEMA_REVISION)

    app.dependency_overrides[check_database_readiness] = database_is_ready

    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["schema_revision"] == EXPECTED_SCHEMA_REVISION


async def test_ready_fails_closed_before_database_initialization(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "dependency_unavailable"


async def test_ready_uses_problem_details_without_internal_error(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    async def database_is_not_ready() -> ReadinessState:
        raise ProblemException(
            status=503,
            code="dependency_unavailable",
            title="Servicio no disponible",
            detail="La API todavía no está lista.",
        )

    app.dependency_overrides[check_database_readiness] = database_is_not_ready

    response = await client.get("/api/v1/health/ready")

    body = response.json()
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["X-Request-ID"] == body["request_id"]
    assert body["code"] == "dependency_unavailable"
    assert body["instance"] == "/api/v1/health/ready"
    assert str(UUID(body["request_id"])) == body["request_id"]
    assert "database" not in str(body).lower()


async def test_unknown_route_uses_non_revealing_problem_details(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/recurso-inexistente")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == "La solicitud no pudo procesarse."


async def test_malformed_request_id_is_not_reflected(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/api/v1/health/live", headers={"X-Request-ID": "valor-controlado-por-cliente"}
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "valor-controlado-por-cliente"
    UUID(response.headers["X-Request-ID"])


async def test_unknown_query_parameter_is_rejected(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health/live?unexpected=SYNTHETIC")

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["errors"] == [
        {
            "location": ["query", "unexpected"],
            "message": "El parámetro no está permitido.",
            "code": "extra_forbidden",
        }
    ]


async def test_framework_validation_uses_problem_details(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    @app.get("/api/v1/_synthetic-validation", include_in_schema=False)
    async def synthetic_validation(limit: int = Query(ge=1, le=100)) -> dict[str, int]:
        return {"limit": limit}

    response = await client.get("/api/v1/_synthetic-validation?limit=invalid")

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "validation_error"
    assert response.json()["errors"][0]["location"] == ["query", "limit"]
    assert "invalid" not in str(response.json()["errors"])


async def test_unexpected_exception_is_generic_problem_details(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    @app.get("/api/v1/_synthetic-failure", include_in_schema=False)
    async def synthetic_failure() -> None:
        raise RuntimeError("detalle interno que nunca debe exponerse")

    response = await client.get("/api/v1/_synthetic-failure")

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "internal_error"
    assert "detalle interno" not in str(response.json())
