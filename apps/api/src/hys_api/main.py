"""Factoría ASGI de la API."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from hys_api import __version__
from hys_api.api.v1.router import router as v1_router
from hys_api.core.config import Settings, get_settings
from hys_api.core.errors import (
    ProblemException,
    http_exception_handler,
    problem_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)
from hys_api.core.request_id import RequestIdMiddleware
from hys_api.core.telemetry import HttpTelemetryMiddleware
from hys_api.db.session import build_engine, build_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(app_settings)
        application.state.db_engine = engine
        application.state.session_factory = build_session_factory(engine)
        try:
            yield
        finally:
            await engine.dispose()

    application = FastAPI(
        title="HYS Gestión API",
        summary="API para la gestión trazable de higiene y seguridad en obras.",
        description="Entorno inicial con datos exclusivamente sintéticos.",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(
        HttpTelemetryMiddleware,
        environment=app_settings.environment,
        log_level=app_settings.log_level,
    )
    application.add_exception_handler(ProblemException, problem_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(Exception, unexpected_exception_handler)
    application.include_router(v1_router)
    return application


app = create_app()
