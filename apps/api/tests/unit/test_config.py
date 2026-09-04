from pydantic import ValidationError

from hys_api.core.config import Settings


def test_database_url_is_required(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("HYS_DATABASE_URL", raising=False)

    try:
        Settings(_env_file=None)
    except ValidationError as exc:
        assert "database_url" in str(exc)
    else:
        raise AssertionError("La configuración aceptó una DB ausente")


def test_only_async_postgresql_is_accepted() -> None:
    try:
        Settings(database_url="postgresql://synthetic:synthetic@db/synthetic")
    except ValidationError as exc:
        assert "postgresql+asyncpg" in str(exc)
    else:
        raise AssertionError("La configuración aceptó un driver no asíncrono")


def test_database_credentials_are_redacted() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://synthetic_user:not-a-secret@db/synthetic"
    )

    assert "not-a-secret" not in repr(settings)
    assert settings.sqlalchemy_database_url.endswith("@db/synthetic")


def test_migration_url_can_use_a_separate_privileged_role() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://hys_app:synthetic@db/synthetic",
        migration_database_url="postgresql+asyncpg://hys_owner:synthetic@db/synthetic",
    )

    assert "hys_owner" in settings.sqlalchemy_migration_database_url
    assert "hys_app" in settings.sqlalchemy_database_url


def test_migration_url_defaults_to_application_url_for_local_tooling() -> None:
    settings = Settings(database_url="postgresql+asyncpg://synthetic:synthetic@db/synthetic")

    assert settings.sqlalchemy_migration_database_url == settings.sqlalchemy_database_url


def test_database_url_requires_a_database_name() -> None:
    try:
        Settings(database_url="postgresql+asyncpg://synthetic:synthetic@db")
    except ValidationError as exc:
        assert "indicar una base" in str(exc)
    else:
        raise AssertionError("La configuración aceptó una URL sin base")


def test_sql_echo_is_rejected_in_production() -> None:
    try:
        Settings(
            environment="production",
            database_echo=True,
            database_url="postgresql+asyncpg://synthetic:synthetic@db/synthetic",
        )
    except ValidationError as exc:
        assert "database_echo" in str(exc)
    else:
        raise AssertionError("La configuración habilitó SQL sensible en producción")
