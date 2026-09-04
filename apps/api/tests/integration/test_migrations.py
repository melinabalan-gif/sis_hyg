from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from hys_api.db.schema import EXPECTED_SCHEMA_REVISION

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_empty_database_migrates_to_expected_revision(migrated_database: str) -> None:
    engine = create_async_engine(migrated_database)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            tables = set(
                await connection.scalars(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = current_schema() ORDER BY tablename"
                    )
                )
            )
    finally:
        await engine.dispose()

    assert revision == EXPECTED_SCHEMA_REVISION
    assert {"alembic_version", "organizations", "worksites"} <= tables


def test_metadata_matches_head(migrated_database: str) -> None:
    api_root = Path(__file__).resolve().parents[2]
    config = Config(str(api_root / "alembic.ini"))
    command.check(config)


def test_initial_revision_downgrades_and_reupgrades(migrated_database: str) -> None:
    api_root = Path(__file__).resolve().parents[2]
    config = Config(str(api_root / "alembic.ini"))

    command.downgrade(config, "base")
    command.upgrade(config, "head")
