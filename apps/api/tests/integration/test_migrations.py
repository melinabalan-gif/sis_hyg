import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from hys_api.api.dependencies import PILOT_ORGANIZATION_ID
from hys_api.db.schema import EXPECTED_SCHEMA_REVISION

pytestmark = pytest.mark.integration

PILOT_TABLES = {
    "audit_controls",
    "audits",
    "contractor_documents",
    "contractors",
    "control_catalog_versions",
    "corrections",
    "documents",
    "document_versions",
    "finding_controls",
    "finding_events",
    "findings",
    "machine_documents",
    "machine_inspections",
    "machine_worksite_assignments",
    "machines",
    "people",
    "person_assignments",
    "person_documents",
    "severity_catalog_versions",
    "verifications",
    "worksite_contractors",
    "worksite_functional_assignments",
    "worksite_documents",
    "worksite_stages",
}


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
    assert PILOT_TABLES <= tables


def test_metadata_matches_head(migrated_database: str) -> None:
    api_root = Path(__file__).resolve().parents[2]
    config = Config(str(api_root / "alembic.ini"))
    command.check(config)


def test_initial_revision_downgrades_and_reupgrades(migrated_database: str) -> None:
    api_root = Path(__file__).resolve().parents[2]
    config = Config(str(api_root / "alembic.ini"))

    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_pilot_revision_downgrades_and_reupgrades(migrated_database: str) -> None:
    api_root = Path(__file__).resolve().parents[2]
    config = Config(str(api_root / "alembic.ini"))

    command.downgrade(config, "20260902_0001")
    command.upgrade(config, "head")


def test_review_version_migration_preserves_unknown_legacy_and_checks_new_links(
    migrated_database: str,
) -> None:
    """Roundtrip the actual constraint and preserve legacy evidence without guessing."""
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    document_id, other_document_id, version_id, other_version_id, legacy_id = (
        uuid4() for _ in range(5)
    )
    other_org = uuid4()
    same_org_document_id, same_org_version_id = uuid4(), uuid4()
    actor = uuid4()

    async def prepare_legacy():
        engine = create_async_engine(migrated_database)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO organizations (id, name, slug) "
                        "VALUES (:id, 'Synthetic', :slug)"
                    ),
                    {"id": other_org, "slug": f"syn-{other_org}"},
                )
                for org, did in [
                    (PILOT_ORGANIZATION_ID, document_id),
                    (other_org, other_document_id),
                    (PILOT_ORGANIZATION_ID, same_org_document_id),
                ]:
                    await connection.execute(
                        text(
                            "INSERT INTO documents (id, organization_id, title, document_type) "
                            "VALUES (:id, :org, 'Synthetic migration evidence', 'SYN')"
                        ),
                        {"id": did, "org": org},
                    )
                for org, did, vid in [
                    (PILOT_ORGANIZATION_ID, document_id, version_id),
                    (other_org, other_document_id, other_version_id),
                    (PILOT_ORGANIZATION_ID, same_org_document_id, same_org_version_id),
                ]:
                    await connection.execute(
                        text(
                            "INSERT INTO document_versions (id, organization_id, document_id, "
                            "version_number, title, document_type, review_status, actor_id) "
                            "VALUES (:id, :org, :doc, 1, 'Synthetic', 'SYN', 'PENDIENTE', :actor)"
                        ),
                        {"id": vid, "org": org, "doc": did, "actor": actor},
                    )
                await connection.execute(
                    text(
                        "INSERT INTO document_reviews (id, organization_id, document_id, "
                        "reviewer_actor_id, reviewer_function, result, foundation) "
                        "VALUES (:id, :org, :doc, :actor, 'AUDITOR', 'APROBADO', 'Legacy unknown')"
                    ),
                    {
                        "id": legacy_id,
                        "org": PILOT_ORGANIZATION_ID,
                        "doc": document_id,
                        "actor": actor,
                    },
                )
        finally:
            await engine.dispose()

    async def inspect_and_check():
        engine = create_async_engine(migrated_database)
        try:
            async with engine.connect() as connection:
                row = (
                    await connection.execute(
                        text(
                            "SELECT document_version_id, foundation FROM document_reviews "
                            "WHERE id=:id"
                        ),
                        {"id": legacy_id},
                    )
                ).one()
                assert tuple(row) == (None, "Legacy unknown")
                validated = await connection.scalar(
                    text(
                        "SELECT convalidated FROM pg_constraint "
                        "WHERE conname='ck_document_reviews_version_required'"
                    )
                )
                assert validated is False
            for org, did, vid, expected in [
                (PILOT_ORGANIZATION_ID, document_id, None, "ck_document_reviews_version_required"),
                (
                    PILOT_ORGANIZATION_ID,
                    document_id,
                    same_org_version_id,
                    "fk_document_reviews_org_document_version",
                ),
                (
                    PILOT_ORGANIZATION_ID,
                    document_id,
                    other_version_id,
                    "fk_document_reviews_org_document_version",
                ),
                (
                    other_org,
                    other_document_id,
                    version_id,
                    "fk_document_reviews_org_document_version",
                ),
            ]:
                with pytest.raises(IntegrityError) as error:
                    async with engine.begin() as connection:
                        await connection.execute(
                            text(
                                "INSERT INTO document_reviews (id, organization_id, document_id, "
                                "document_version_id, reviewer_actor_id, reviewer_function, "
                                "result, foundation) "
                                "VALUES (:id,:org,:doc,:version,:actor,'AUDITOR','APROBADO',"
                                "'Synthetic')"
                            ),
                            {"id": uuid4(), "org": org, "doc": did, "version": vid, "actor": actor},
                        )
                assert expected in str(error.value)
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO document_reviews (id, organization_id, document_id, "
                        "document_version_id, reviewer_actor_id, reviewer_function, "
                        "result, foundation) "
                        "VALUES (:id,:org,:doc,:version,:actor,'AUDITOR','APROBADO',"
                        "'Synthetic')"
                    ),
                    {
                        "id": uuid4(),
                        "org": PILOT_ORGANIZATION_ID,
                        "doc": document_id,
                        "version": version_id,
                        "actor": actor,
                    },
                )
        finally:
            await engine.dispose()

    command.downgrade(config, "20261001_0011")
    asyncio.run(prepare_legacy())
    command.upgrade(config, "head")
    asyncio.run(inspect_and_check())
    command.downgrade(config, "20261001_0011")
    command.upgrade(config, "head")
    asyncio.run(inspect_and_check())
