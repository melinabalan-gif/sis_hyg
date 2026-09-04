"""Endpoints operativos: liveness independiente y readiness estricta."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from hys_api import __version__
from hys_api.api.dependencies import reject_query_parameters
from hys_api.core.errors import problem_openapi_response
from hys_api.db.readiness import ReadinessState, check_database_readiness


class LiveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: Literal["hys-api"] = "hys-api"
    version: str


class ReadyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready"] = "ready"
    service: Literal["hys-api"] = "hys-api"
    version: str
    schema_revision: str


router = APIRouter(
    prefix="/health", tags=["health"], dependencies=[Depends(reject_query_parameters)]
)


@router.get(
    "/live",
    operation_id="health_live",
    response_model=LiveResponse,
    responses={422: problem_openapi_response("Parámetro de consulta no permitido")},
    summary="Verifica que el proceso responda",
)
async def live() -> LiveResponse:
    return LiveResponse(version=__version__)


@router.get(
    "/ready",
    operation_id="health_ready",
    response_model=ReadyResponse,
    responses={
        422: problem_openapi_response("Parámetro de consulta no permitido"),
        503: problem_openapi_response("DB no disponible o esquema incompatible"),
    },
    summary="Verifica DB y revisión de esquema",
)
async def ready(
    state: Annotated[ReadinessState, Depends(check_database_readiness)],
) -> ReadyResponse:
    return ReadyResponse(version=__version__, schema_revision=state.schema_revision)
