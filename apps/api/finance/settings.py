"""Application settings, read once from the repo-root .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    # Secrets stay out of repr, so a failing assert or a log line never prints them.
    supabase_db_url: str | None = Field(default=None, repr=False)
    supabase_db_url_readonly: str | None = Field(default=None, repr=False)
    typesafe_api_key: str | None = Field(default=None, repr=False)
    xai_api_key: str | None = Field(default=None, repr=False)
    langfuse_public_key: str | None = Field(default=None, repr=False)
    langfuse_secret_key: str | None = Field(default=None, repr=False)
    langfuse_base_url: str = "https://cloud.langfuse.com"
    cors_origins: list[str] = ["http://localhost:3000"]
    transfer_pattern: str = "TRASPASO|TRANSFER|BIZUM|TRF"
    transfer_window_days: int = 2
    jev_concurrency: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
