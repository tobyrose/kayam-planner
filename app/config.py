from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Kayam Seasonal Planning System"
    app_env: str = "development"
    debug: bool = Field(default=False, validation_alias="KAYAM_DEBUG")
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "sqlite:///./instance/kayam.db"
    secret_key: str = "development-only-change-me"
    default_timezone: str = "Europe/London"
    routing_provider: str = "manual"
    openrouteservice_api_key: str | None = None
    route_amber_margin_minutes: int = Field(default=360, ge=0)
    route_green_margin_minutes: int = Field(default=1440, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
