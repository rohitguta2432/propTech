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

    # LLM parsing fallback — Gemma 4 31B via OpenRouter free tier ($0/M tokens).
    # Get a free key at https://openrouter.ai → no credit card needed.
    # If unset, scrapers fall back to regex-only (still works, just less coverage).
    openrouter_api_key: str | None = None
    openrouter_model: str = "google/gemma-4-31b-it:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"


settings = Settings()
