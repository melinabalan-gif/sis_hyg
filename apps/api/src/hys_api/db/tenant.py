"""Contexto transaccional obligatorio para las políticas RLS."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    organization_id: UUID
    actor_id: UUID | None = None
    worksite_ids: frozenset[UUID] = frozenset()


async def apply_authorization_context(session: AsyncSession, context: AuthorizationContext) -> None:
    """Fija el tenant sólo durante la transacción actual.

    Los repositorios futuros recibirán ``AuthorizationContext`` en lugar de un
    organization_id procedente de la solicitud.
    """

    await session.execute(
        text("SELECT set_config('app.current_organization_id', :organization_id, true)"),
        {"organization_id": str(context.organization_id)},
    )
