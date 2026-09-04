from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hys_api.db.tenant import AuthorizationContext, apply_authorization_context


class RecordingSession:
    def __init__(self) -> None:
        self.parameters: dict[str, str] | None = None

    async def execute(self, _statement, parameters) -> None:  # type: ignore[no-untyped-def]
        self.parameters = parameters


@pytest.mark.asyncio
async def test_tenant_context_comes_from_authorization_context() -> None:
    organization_id = UUID("10000000-0000-0000-0000-000000000001")
    session = RecordingSession()

    await apply_authorization_context(
        cast(AsyncSession, session), AuthorizationContext(organization_id=organization_id)
    )

    assert session.parameters == {"organization_id": str(organization_id)}
