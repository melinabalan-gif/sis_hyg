"""Fixtures sin datos ni credenciales reales."""

import os
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

SYNTHETIC_DATABASE_URL = (
    "postgresql+asyncpg://synthetic_user:synthetic_password@127.0.0.1:5432/hys_synthetic"
)
os.environ.setdefault(
    "HYS_DATABASE_URL", os.environ.get("HYS_TEST_DATABASE_URL", SYNTHETIC_DATABASE_URL)
)
os.environ.setdefault("HYS_ENVIRONMENT", "test")

from hys_api.core.config import Settings  # noqa: E402
from hys_api.main import create_app  # noqa: E402


@pytest.fixture
def app() -> FastAPI:
    settings = Settings(database_url=SYNTHETIC_DATABASE_URL, environment="test")
    return create_app(settings)


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as value:
        yield value
