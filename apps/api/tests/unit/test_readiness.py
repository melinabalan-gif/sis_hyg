from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hys_api.core.errors import ProblemException
from hys_api.db.readiness import check_database_readiness
from hys_api.db.schema import EXPECTED_SCHEMA_REVISION


class StubSession:
    def __init__(self, revision: str | None, *, fails: bool = False) -> None:
        self.revision = revision
        self.fails = fails

    async def execute(self, _statement) -> None:  # type: ignore[no-untyped-def]
        if self.fails:
            raise OSError("detalle interno sintético")

    async def scalar(self, _statement) -> str | None:  # type: ignore[no-untyped-def]
        return self.revision


@pytest.mark.asyncio
async def test_ready_accepts_the_expected_revision() -> None:
    state = await check_database_readiness(
        cast(AsyncSession, StubSession(EXPECTED_SCHEMA_REVISION))
    )
    assert state.schema_revision == EXPECTED_SCHEMA_REVISION


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("session", "expected_code"),
    [
        (StubSession("revision-distinta"), "schema_incompatible"),
        (StubSession(None, fails=True), "dependency_unavailable"),
    ],
)
async def test_ready_fails_closed(session: StubSession, expected_code: str) -> None:
    with pytest.raises(ProblemException) as raised:
        await check_database_readiness(cast(AsyncSession, session))

    assert raised.value.status == 503
    assert raised.value.code == expected_code
    assert "interno" not in raised.value.detail
