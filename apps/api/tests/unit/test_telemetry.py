import json

from hys_api.core.telemetry import build_http_event


def test_http_event_is_structured_and_contains_no_request_payload() -> None:
    event = json.loads(
        build_http_event(
            environment="test",
            request_id="00000000-0000-0000-0000-000000000099",
            method="GET",
            route="/api/v1/health/live",
            status=200,
            duration_ms=1.23456,
        )
    )

    assert event["route"] == "/api/v1/health/live"
    assert event["duration_ms"] == 1.235
    assert event["timestamp"].endswith("Z")
    assert {"body", "query", "headers", "cookies"}.isdisjoint(event)
