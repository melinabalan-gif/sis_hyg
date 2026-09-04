"""Dependencias HTTP compartidas."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from hys_api.core.errors import ProblemException, ProblemFieldError
from hys_api.db.session import get_session
from hys_api.db.tenant import AuthorizationContext, apply_authorization_context

PILOT_ORGANIZATION_ID = UUID("00000000-0000-4000-8000-000000000001")


class PilotRole(StrEnum):
    """Roles acotados del recorrido sintético del piloto."""

    AUDITOR = "AUDITOR"
    TECNICO = "TECNICO"
    RESPONSABLE_HYS = "RESPONSABLE_HYS"
    CONTRATISTA = "CONTRATISTA"


@dataclass(frozen=True, slots=True)
class PilotActor:
    """Identidad sintética fija; no reemplaza la autenticación de producción."""

    key: str
    id: UUID
    role: PilotRole
    label: str = "Actor sintético"
    profession_code: str | None = None
    permission_scope: str = "WORKSITE"


PILOT_ACTORS = MappingProxyType(
    {
        "auditor": PilotActor(
            key="auditor",
            id=UUID("00000000-0000-4000-8000-000000000001"),
            role=PilotRole.AUDITOR,
            label="Auditor delegado proyecto",
            profession_code="TECNICO_HYS",
        ),
        "tecnico": PilotActor(
            key="tecnico",
            id=UUID("00000000-0000-4000-8000-000000000002"),
            role=PilotRole.TECNICO,
            label="Técnico H&S contratista principal",
            profession_code="TECNICO_HYS",
        ),
        "responsable": PilotActor(
            key="responsable",
            id=UUID("00000000-0000-4000-8000-000000000003"),
            role=PilotRole.RESPONSABLE_HYS,
            label="Responsable H&S proyecto",
            profession_code="LICENCIADO_HYS",
        ),
        "responsable-suplente": PilotActor(
            key="responsable-suplente",
            id=UUID("00000000-0000-4000-8000-000000000004"),
            role=PilotRole.RESPONSABLE_HYS,
            label="Profesional H&S contratista principal",
            profession_code="LICENCIADO_HYS",
        ),
        "contratista-principal": PilotActor(
            key="contratista-principal",
            id=UUID("00000000-0000-4000-8000-000000000005"),
            role=PilotRole.CONTRATISTA,
            label="Contratista principal",
            profession_code="CONTRATISTA",
        ),
    }
)


@dataclass(frozen=True, slots=True)
class PilotRequestContext:
    """Actor y sesión tenant-aware compartidos por un request del piloto."""

    actor: PilotActor
    session: AsyncSession


async def get_pilot_actor(
    pilot_actor_key: Annotated[str | None, Header(alias="X-Pilot-Actor")] = None,
) -> PilotActor:
    """Resuelve únicamente las identidades sintéticas permitidas para el piloto."""

    actor = PILOT_ACTORS.get(pilot_actor_key or "")
    if actor is None:
        raise ProblemException(
            status=401,
            code="pilot_authentication_required",
            title="Se requiere identidad del piloto",
            detail="Indicá un actor sintético válido mediante X-Pilot-Actor.",
        )
    return actor


async def get_pilot_context(
    actor: Annotated[PilotActor, Depends(get_pilot_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AsyncIterator[PilotRequestContext]:
    """Abre la UoW y fija el tenant mediante ``SET LOCAL`` antes de consultar."""

    async with session.begin():
        await apply_authorization_context(
            session,
            AuthorizationContext(
                organization_id=PILOT_ORGANIZATION_ID,
                actor_id=actor.id,
            ),
        )
        yield PilotRequestContext(actor=actor, session=session)


def require_pilot_role(actor: PilotActor, *allowed_roles: PilotRole) -> None:
    """Aplica los permisos mínimos de servidor del recorrido sintético."""

    if actor.role not in allowed_roles:
        raise ProblemException(
            status=403,
            code="pilot_permission_denied",
            title="Acceso denegado",
            detail="El rol sintético no permite realizar esta acción.",
        )


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
