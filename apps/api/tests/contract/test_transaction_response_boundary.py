import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from hys_api.api import dependencies
from hys_api.db.session import get_session
from hys_api.modules.pilot.schemas import WorksiteSummary
from hys_api.modules.pilot.service import PilotService


@pytest.mark.parametrize("commit_fails", [False, True])
async def test_creation_response_waits_for_transaction_commit(app, monkeypatch, commit_fails):
    events = []
    commit_started = asyncio.Event()
    release_commit = asyncio.Event()
    committed = False
    statuses = []

    @asynccontextmanager
    async def transaction():
        nonlocal committed
        yield
        events.append("commit_started")
        commit_started.set()
        await release_commit.wait()
        if commit_fails:
            events.append("commit_failed")
            raise RuntimeError("Synthetic commit failure")
        committed = True
        events.append("commit_finished")

    async def session_dependency():
        yield SimpleNamespace(begin=transaction)

    async def tenant_context(*_args, **_kwargs):
        events.append("tenant_context")

    async def create_worksite(_service, payload):
        events.append("materialized_dto")
        now = datetime.now(UTC)
        return WorksiteSummary(
            id=uuid4(),
            code="SYN-COMMIT",
            name=payload.name,
            address=payload.address,
            jurisdiction=payload.jurisdiction,
            status="ACTIVE",
            version=1,
            created_at=now,
            updated_at=now,
        )

    app.dependency_overrides[get_session] = session_dependency
    monkeypatch.setattr(dependencies, "apply_authorization_context", tenant_context)
    monkeypatch.setattr(PilotService, "create_worksite", create_worksite)
    body = json.dumps(
        {"name": "Synthetic commit", "address": "Synthetic address", "jurisdiction": "Synthetic"}
    ).encode()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            statuses.append((message["status"], committed))
            events.append(f"response_{message['status']}")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/worksites",
        "raw_path": b"/api/v1/worksites",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json"), (b"x-pilot-actor", b"responsable")],
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
        "root_path": "",
    }
    task = asyncio.create_task(app(scope, receive, send))
    try:
        await asyncio.wait_for(commit_started.wait(), timeout=2)
        # The actual ASGI send boundary must not advertise success while COMMIT waits.
        early_statuses = list(statuses)
    finally:
        release_commit.set()
        if commit_fails:
            with pytest.raises(RuntimeError, match="Synthetic commit failure"):
                await task
        else:
            await task
        app.dependency_overrides.clear()

    assert early_statuses == [], events
    if commit_fails:
        assert statuses == [(500, False)], events
    else:
        assert statuses == [(201, True)], events
        assert events.index("commit_finished") < events.index("response_201")
