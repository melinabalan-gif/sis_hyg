"""Dependencias HTTP compartidas."""

from fastapi import Request

from hys_api.core.errors import ProblemException, ProblemFieldError


async def reject_query_parameters(request: Request) -> None:
    """Los endpoints sin filtros fallan ante parámetros no declarados."""

    if not request.query_params:
        return
    errors = [
        ProblemFieldError(
            location=["query", name],
            message="El parámetro no está permitido.",
            code="extra_forbidden",
        )
        for name in sorted(set(request.query_params.keys()))
    ]
    raise ProblemException(
        status=422,
        code="validation_error",
        title="La solicitud no es válida",
        detail="Revisá los campos indicados antes de reintentar.",
        errors=errors,
    )
