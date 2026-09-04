"""Problem Details RFC 9457 sin información sensible."""

from http import HTTPStatus
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException

from hys_api.core.request_id import REQUEST_ID_HEADER

PROBLEM_BASE_URL = "https://hys.invalid/problems"


class ProblemFieldError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: list[str | int]
    message: str
    code: str


class ProblemDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str
    request_id: str
    errors: list[ProblemFieldError] = Field(default_factory=list)


class ProblemException(Exception):
    def __init__(
        self,
        *,
        status: int,
        code: str,
        title: str,
        detail: str,
        errors: list[ProblemFieldError] | None = None,
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.errors = errors or []


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else str(uuid4())


def _problem_response(
    request: Request,
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    errors: list[ProblemFieldError] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    problem = ProblemDetails(
        type=f"{PROBLEM_BASE_URL}/{code.replace('_', '-')}",
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        code=code,
        request_id=request_id,
        errors=errors or [],
    )
    return JSONResponse(
        status_code=status,
        content=problem.model_dump(mode="json"),
        media_type="application/problem+json",
        headers={REQUEST_ID_HEADER: request_id},
    )


async def problem_exception_handler(request: Request, exc: ProblemException) -> JSONResponse:
    return _problem_response(
        request,
        status=exc.status,
        code=exc.code,
        title=exc.title,
        detail=exc.detail,
        errors=exc.errors,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        ProblemFieldError(
            location=[part for part in error["loc"] if isinstance(part, (str, int))],
            message=str(error["msg"]),
            code=str(error["type"]),
        )
        for error in exc.errors()
    ]
    return _problem_response(
        request,
        status=422,
        code="validation_error",
        title="La solicitud no es válida",
        detail="Revisá los campos indicados antes de reintentar.",
        errors=errors,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    status = exc.status_code
    try:
        default_title = HTTPStatus(status).phrase
    except ValueError:
        default_title = "Error HTTP"
    titles = {
        401: "Se requiere autenticación",
        403: "Acceso denegado",
        404: "Recurso no encontrado",
        405: "Método no permitido",
    }
    return _problem_response(
        request,
        status=status,
        code=f"http_{status}",
        title=titles.get(status, default_title),
        detail="La solicitud no pudo procesarse.",
    )


async def unexpected_exception_handler(request: Request, _exc: Exception) -> JSONResponse:
    return _problem_response(
        request,
        status=500,
        code="internal_error",
        title="Error interno",
        detail="La solicitud no pudo completarse.",
    )


def problem_openapi_response(description: str) -> dict[str, Any]:
    schema = ProblemDetails.model_json_schema()
    definitions = schema.pop("$defs", {})

    def inline_local_definitions(value: Any) -> Any:
        if isinstance(value, list):
            return [inline_local_definitions(item) for item in value]
        if not isinstance(value, dict):
            return value

        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            definition_name = reference.removeprefix("#/$defs/")
            definition = definitions.get(definition_name)
            if definition is None:
                raise ValueError(f"Referencia JSON Schema desconocida: {reference}")
            return inline_local_definitions(definition)

        return {key: inline_local_definitions(item) for key, item in value.items()}

    return {
        "description": description,
        "content": {"application/problem+json": {"schema": inline_local_definitions(schema)}},
    }
