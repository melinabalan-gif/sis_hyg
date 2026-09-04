"""Base PostgreSQL aislada requerida por las pruebas de integración."""

import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[str]:
    database_url = os.environ.get("HYS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("HYS_TEST_DATABASE_URL no fue configurada")

    database_name = make_url(database_url).database or ""
    normalized_name = database_name.lower()
    destructive_opt_in = os.environ.get("HYS_ALLOW_DESTRUCTIVE_TEST_DATABASE")
    has_test_name = re.search(r"(?:^|_)(?:test|synthetic)(?:_|$)", normalized_name)
    if destructive_opt_in != "1" or has_test_name is None:
        pytest.fail(
            "Las pruebas destructivas requieren HYS_ALLOW_DESTRUCTIVE_TEST_DATABASE=1 "
            "y una base aislada cuyo nombre contenga el segmento 'test' o 'synthetic'; "
            "no se ejecutará downgrade"
        )

    api_root = Path(__file__).resolve().parents[2]
    config = Config(str(api_root / "alembic.ini"))
    previous_migration_url = os.environ.get("HYS_MIGRATION_DATABASE_URL")
    # Alembic usa exclusivamente la credencial propietaria. HYS_DATABASE_URL
    # conserva la conexión no privilegiada de hys_app durante toda la suite.
    os.environ["HYS_MIGRATION_DATABASE_URL"] = database_url
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        yield database_url
    finally:
        try:
            command.downgrade(config, "base")
        finally:
            if previous_migration_url is None:
                os.environ.pop("HYS_MIGRATION_DATABASE_URL", None)
            else:
                os.environ["HYS_MIGRATION_DATABASE_URL"] = previous_migration_url


@pytest.fixture(scope="session")
def app_database_url(migrated_database: str) -> str:
    database_url = os.environ.get("HYS_DATABASE_URL")
    if database_url is None:
        pytest.fail("HYS_DATABASE_URL debe configurar la conexión runtime de hys_app")

    owner = make_url(migrated_database)
    runtime = make_url(database_url)
    if runtime.username != "hys_app":
        pytest.fail("HYS_DATABASE_URL debe autenticar exactamente como hys_app")
    if owner.username == runtime.username:
        pytest.fail("El propietario/migrador y hys_app deben ser usuarios distintos")

    owner_endpoint = (owner.host, owner.port, owner.database)
    runtime_endpoint = (runtime.host, runtime.port, runtime.database)
    if runtime_endpoint != owner_endpoint:
        pytest.fail(
            "HYS_DATABASE_URL y HYS_TEST_DATABASE_URL deben apuntar a la misma base aislada"
        )

    return database_url
