"""Motor y sesiones asíncronas de SQLAlchemy."""

from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from hys_api.core.config import Settings
from hys_api.core.errors import ProblemException

SessionFactory = async_sessionmaker[AsyncSession]


def build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.sqlalchemy_database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
    )


def build_session_factory(engine: AsyncEngine) -> SessionFactory:
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory_value = getattr(request.app.state, "session_factory", None)
    if factory_value is None:
        raise ProblemException(
            status=503,
            code="dependency_unavailable",
            title="Servicio no disponible",
            detail="La API todavía no está lista.",
        )
    factory = cast(SessionFactory, factory_value)
    async with factory() as session:
        yield session
