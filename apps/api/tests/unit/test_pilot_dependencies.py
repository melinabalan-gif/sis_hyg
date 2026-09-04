from uuid import UUID

import pytest

from hys_api.api.dependencies import (
    PILOT_ACTORS,
    PILOT_ORGANIZATION_ID,
    PilotRole,
    get_pilot_actor,
    require_pilot_role,
)
from hys_api.core.errors import ProblemException


@pytest.mark.asyncio
async def test_pilot_actor_header_resolves_only_stable_synthetic_actors() -> None:
    actor = await get_pilot_actor("responsable-suplente")

    assert actor.id == UUID("00000000-0000-4000-8000-000000000004")
    assert actor.role is PilotRole.RESPONSABLE_HYS
    assert PILOT_ORGANIZATION_ID == UUID("00000000-0000-4000-8000-000000000001")


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, "", "administrador", "RESPONSABLE"])
async def test_unknown_pilot_actor_is_unauthorized(value: str | None) -> None:
    with pytest.raises(ProblemException) as raised:
        await get_pilot_actor(value)

    assert raised.value.status == 401
    assert raised.value.code == "pilot_authentication_required"


def test_pilot_role_guard_denies_unlisted_role() -> None:
    with pytest.raises(ProblemException) as raised:
        require_pilot_role(PILOT_ACTORS["auditor"], PilotRole.TECNICO)

    assert raised.value.status == 403
    assert raised.value.code == "pilot_permission_denied"
