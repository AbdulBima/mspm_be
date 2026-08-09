"""
app.core.config
================
Centralized, validated runtime configuration. Replaces ad hoc
`os.environ[...]` reads scattered across modules with a single
pydantic-settings model: required variables now fail fast with a clear
validation error naming the missing field, instead of a bare KeyError deep
in an import chain.

`get_settings()` is cached so the environment is read exactly once per
process; tests can call `get_settings.cache_clear()` after monkeypatching
`os.environ` to force a re-read.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General ---
    env: str = Field("production", alias="ENV")
    port: int = Field(8000, alias="PORT")

    # --- Database ---
    mongo_uri: str = Field(alias="MONGO_URI")
    database_name: str = Field("sprint_ops", alias="DATABASE_NAME")

    # --- Auth ---
    secret_key: str = Field(alias="SECRET_KEY")
    algorithm: str = Field("HS256", alias="ALGORITHM")
    pm_token_expire_minutes: int = Field(10080, alias="PM_TOKEN_EXPIRE_MINUTES")  # 7 days
    pm_tracker_invite_code: str | None = Field(None, alias="PM_TRACKER_INVITE_CODE")

    # --- CORS ---
    allowed_origins_raw: str = Field("", alias="ALLOWED_ORIGINS")

    # --- Optional AI narrative on generated reports ---
    groq_api_key: str | None = Field(None, alias="GROQ_API_KEY")

    @property
    def is_dev(self) -> bool:
        return self.env == "development"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins_raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
