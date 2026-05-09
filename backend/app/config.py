"""Application settings loaded from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "dev"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    # Wired up later in Sprint 1
    database_url: str | None = None
    redis_url: str | None = None
    rera_karnataka_base: str = "https://rera.karnataka.gov.in"


settings = Settings()
