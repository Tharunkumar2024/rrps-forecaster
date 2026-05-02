"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration sourced from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rrps_db"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/rrps_db"
    app_name: str = "RRPS Forecaster"
    app_env: str = "development"
    debug: bool = True


def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
