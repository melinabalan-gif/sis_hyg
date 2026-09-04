from uuid import UUID

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from hys_api.modules.organizations.models import Organization
from hys_api.modules.worksites.models import Worksite

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_public_has_no_table_privileges_and_app_role_is_not_privileged(
    migrated_database: str,
    app_database_url: str,
) -> None:
    owner_engine = create_async_engine(migrated_database)
    app_engine = create_async_engine(app_database_url)
    try:
        async with owner_engine.begin() as connection:
            public_grants = (
                await connection.execute(
                    text(
                        "SELECT table_name, privilege_type "
                        "FROM information_schema.table_privileges "
                        "WHERE table_schema = current_schema() AND grantee = 'PUBLIC' "
                        "AND table_name IN ('alembic_version', 'organizations', 'worksites')"
                    )
                )
            ).all()
            app_role = (
                await connection.execute(
                    text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'hys_app'")
                )
            ).one_or_none()

            assert app_role is not None, "El provisionador debe crear el rol hys_app"
        async with app_engine.begin() as connection:
            identity = (await connection.execute(text("SELECT current_user, session_user"))).one()
            grants = (
                await connection.execute(
                    text(
                        "SELECT "
                        "has_table_privilege(current_user, 'alembic_version', 'SELECT'), "
                        "has_table_privilege(current_user, 'organizations', 'SELECT'), "
                        "has_table_privilege(current_user, 'organizations', 'INSERT'), "
                        "has_table_privilege(current_user, 'worksites', 'SELECT'), "
                        "has_table_privilege(current_user, 'worksites', 'INSERT'), "
                        "has_table_privilege(current_user, 'worksites', 'UPDATE'), "
                        "has_table_privilege(current_user, 'worksites', 'DELETE')"
                    )
                )
            ).one()
    finally:
        await app_engine.dispose()
        await owner_engine.dispose()

    assert public_grants == []
    assert app_role == (False, False)
    assert identity == ("hys_app", "hys_app")
    assert grants == (True, True, False, True, True, True, False)


@pytest.mark.asyncio
async def test_rls_is_enabled_forced_and_filters_both_tenants(
    migrated_database: str,
    app_database_url: str,
) -> None:
    owner_engine = create_async_engine(migrated_database)
    app_engine = create_async_engine(app_database_url)
    organization_a = UUID("10000000-0000-0000-0000-000000000001")
    organization_b = UUID("20000000-0000-0000-0000-000000000002")
    worksite_a = UUID("10000000-0000-0000-0000-000000000011")
    worksite_b = UUID("20000000-0000-0000-0000-000000000022")

    try:
        async with owner_engine.begin() as connection:
            policy_rows = (
                await connection.execute(
                    text(
                        "SELECT relname, relrowsecurity, relforcerowsecurity "
                        "FROM pg_class WHERE relname IN ('organizations', 'worksites')"
                    )
                )
            ).all()
            policies = set(
                await connection.scalars(
                    text(
                        "SELECT policyname FROM pg_policies "
                        "WHERE tablename IN ('organizations', 'worksites')"
                    )
                )
            )
            await connection.execute(
                Organization.__table__.insert(),
                [
                    {"id": organization_a, "name": "Organización SYN A", "slug": "syn-a"},
                    {"id": organization_b, "name": "Organización SYN B", "slug": "syn-b"},
                ],
            )
            await connection.execute(
                Worksite.__table__.insert(),
                [
                    {
                        "id": worksite_a,
                        "organization_id": organization_a,
                        "code": "SYN-A-001",
                        "name": "Obra sintética A",
                    },
                    {
                        "id": worksite_b,
                        "organization_id": organization_b,
                        "code": "SYN-B-001",
                        "name": "Obra sintética B",
                    },
                ],
            )

        assert {(row[0], row[1], row[2]) for row in policy_rows} == {
            ("organizations", True, True),
            ("worksites", True, True),
        }
        assert policies == {
            "organizations_tenant_isolation",
            "worksites_tenant_isolation",
        }

        async with app_engine.begin() as connection:
            organizations_without_context = set(await connection.scalars(select(Organization.id)))
            worksites_without_context = set(await connection.scalars(select(Worksite.id)))

        assert organizations_without_context == set()
        assert worksites_without_context == set()

        async with app_engine.begin() as connection:
            effective_role = (
                await connection.execute(
                    text(
                        "SELECT current_user, session_user, r.rolsuper, r.rolbypassrls "
                        "FROM pg_roles r WHERE r.rolname = current_user"
                    )
                )
            ).one()
            await connection.execute(
                text("SELECT set_config('app.current_organization_id', :tenant, true)"),
                {"tenant": str(organization_a)},
            )
            visible_organizations = set(await connection.scalars(select(Organization.id)))
            visible_worksites = set(await connection.scalars(select(Worksite.id)))

        assert effective_role[0] == "hys_app"
        assert effective_role[1] == "hys_app"
        assert effective_role[2] is False
        assert effective_role[3] is False
        assert visible_organizations == {organization_a}
        assert visible_worksites == {worksite_a}
        assert organization_b not in visible_organizations
        assert worksite_b not in visible_worksites

        with pytest.raises(DBAPIError):
            async with app_engine.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('app.current_organization_id', :tenant, true)"),
                    {"tenant": str(organization_a)},
                )
                await connection.execute(
                    Worksite.__table__.insert(),
                    {
                        "id": UUID("20000000-0000-0000-0000-000000000099"),
                        "organization_id": organization_b,
                        "code": "SYN-CROSS-TENANT",
                        "name": "Obra sintética fuera de tenant",
                    },
                )
    finally:
        await app_engine.dispose()
        await owner_engine.dispose()
