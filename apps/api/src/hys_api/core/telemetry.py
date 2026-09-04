"""Telemetría HTTP estructurada, acotada y libre de payloads."""

import json
import logging
from datetime import UTC, datetime
from time import monotonic

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from hys_api import __version__


def configure_http_logger(level: str) -> logging.Logger:
    logger = logging.getLogger("hys_api.http")
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    return logger


def build_http_event(
    *,
    environment: str,
    request_id: str,
    method: str,
    route: str,
    status: int,
    duration_ms: float,
) -> str:
    return json.dumps(
        {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": "INFO" if status < 500 else "ERROR",
            "service": "hys-api",
            "version": __version__,
            "environment": environment,
            "event": "http_request_completed",
            "request_id": request_id,
            "method": method,
            "route": route,
            "status": status,
            "duration_ms": round(duration_ms, 3),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


class HttpTelemetryMiddleware:
    """Registra sólo la plantilla de ruta; nunca URL, query, headers o body."""

    def __init__(self, app: ASGIApp, *, environment: str, log_level: str) -> None:
        self.app = app
        self.environment = environment
        self.logger = configure_http_logger(log_level)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_at = monotonic()
        status = 500

        async def capture_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            route_object = scope.get("route")
            route = str(getattr(route_object, "path", "unmatched"))
            state = scope.get("state") or {}
            request_id = state.get("request_id", "unavailable")
            duration_ms = (monotonic() - started_at) * 1000
            event = build_http_event(
                environment=self.environment,
                request_id=str(request_id),
                method=scope.get("method", "UNKNOWN"),
                route=route,
                status=status,
                duration_ms=duration_ms,
            )
            self.logger.log(logging.ERROR if status >= 500 else logging.INFO, event)
