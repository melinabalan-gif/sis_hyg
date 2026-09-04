"""Verificación de DB y compatibilidad de esquema."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from hys_api.core.errors import ProblemException
from hys_api.db.schema import EXPECTED_SCHEMA_REVISION
from hys_api.db.session import get_session


@dataclass(frozen=True, slots=True)
class ReadinessState:
    schema_revision: str


async def check_database_readiness(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReadinessState:
    try:
        await session.execute(text("SELECT 1"))
        revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        raise ProblemException(
            status=503,
            code="dependency_unavailable",
            title="Servicio no disponible",
            detail="La API todavía no está lista.",
        ) from exc

    if revision != EXPECTED_SCHEMA_REVISION:
        raise ProblemException(
            status=503,
            code="schema_incompatible",
            title="Servicio no disponible",
            detail="La API todavía no está lista.",
        )
    return ReadinessState(schema_revision=revision)
