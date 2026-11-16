"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the SmartShopper API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SmartShopper"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = "/api"

    # SQLite path is relative to the backend working directory by default.
    database_url: str = "sqlite:///./smartshopper.db"

    # Comma-separated origins for browser clients (Vite dev server).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Reserved for Phase 6 — kept here so .env.example stays accurate.
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    ai_provider: str = "groq"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
