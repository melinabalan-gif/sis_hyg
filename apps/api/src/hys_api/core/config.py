"""Configuración validada exclusivamente desde el entorno."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    """Configuración del proceso API.

    La URL se modela como secreto para evitar que una representación accidental
    exponga credenciales. Sólo se admite el driver asíncrono de PostgreSQL.
    """

    model_config = SettingsConfigDict(
        env_prefix="HYS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
    database_url: SecretStr
    migration_database_url: SecretStr | None = None
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=5, ge=0, le=50)
    database_pool_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    database_echo: bool = False

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("database_url", "migration_database_url", mode="before")
    @classmethod
    def require_async_postgresql(cls, value: object) -> object:
        if value is None:
            return value
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(raw_value, str):
            raise ValueError("database_url debe ser una URL")
        try:
            url = make_url(raw_value)
        except ArgumentError as exc:
            raise ValueError("database_url no es una URL válida") from exc
        if url.drivername != "postgresql+asyncpg":
            raise ValueError("database_url debe usar postgresql+asyncpg")
        if not url.database:
            raise ValueError("database_url debe indicar una base de datos")
        return value

    @model_validator(mode="after")
    def prohibit_sql_logging_in_production(self) -> Self:
        if self.environment == "production" and self.database_echo:
            raise ValueError("database_echo no puede habilitarse en producción")
        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        return self.database_url.get_secret_value()

    @property
    def sqlalchemy_migration_database_url(self) -> str:
        if self.migration_database_url is None:
            return self.sqlalchemy_database_url
        return self.migration_database_url.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
