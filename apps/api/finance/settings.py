"""Application settings, read once from the repo-root .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

ReasoningEffort = Literal["low", "medium", "high", "xhigh"]


class ChatSettings(BaseModel):
    """The chat agent's knobs (slice 4 spec, section 12). Override any of them from .env with
    CHAT__<FIELD>, for example CHAT__REASONING_EFFORT=medium."""

    model: str = Field(default="xai:grok-4.7", description="Agent model, as provider:model")
    reasoning_effort: ReasoningEffort = "high"
    summary_model: str = "xai:grok-4.7"
    summary_reasoning_effort: ReasoningEffort = "medium"
    title_model: str = Field(
        default="xai:grok-4.20-non-reasoning",
        description="A model without reasoning for chat titles (provisional choice)",
    )
    max_retries: int = Field(default=2, ge=0, le=5, description="Model client retries on 429/5xx")
    summary_trigger_tokens: int = Field(default=150_000, ge=10_000)
    summary_keep_messages: int = Field(default=20, ge=2)
    clear_tool_results_trigger_tokens: int = Field(default=15_000, ge=1_000)
    clear_tool_results_keep: int = Field(default=4, ge=1)
    max_sql_calls_per_turn: int = Field(default=8, ge=1, le=30)
    max_model_calls_per_turn: int = Field(default=12, ge=2, le=60)
    # A query costs about 7 graph steps (model, tools and the middleware nodes around them):
    # 120 stays a backstop above max_model_calls_per_turn, never the limit a turn meets first.
    recursion_limit: int = Field(default=120, ge=10, le=500, description="Backstop only")
    sql_timeout_seconds: int = Field(default=10, ge=1, le=60)
    sql_row_limit: int = Field(default=200, ge=1, le=5_000)
    sql_rows_shown: int = Field(default=50, ge=1, le=500)
    sql_max_chars: int = Field(default=8_000, ge=500, le=100_000)
    pool_timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Seconds a chat database call waits for a connection before it fails",
    )
    title_max_chars: int = Field(default=60, ge=20, le=200)
    user_id: str = Field(default="local", description="Langfuse user id")

    @model_validator(mode="after")
    def _limits_fit_together(self) -> Self:
        # Each query needs a model call before it, and the answer needs one more.
        if self.max_model_calls_per_turn <= self.max_sql_calls_per_turn:
            raise ValueError("max_model_calls_per_turn must be above max_sql_calls_per_turn")
        if self.sql_rows_shown > self.sql_row_limit:
            raise ValueError("sql_rows_shown cannot be above sql_row_limit")
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", extra="ignore", env_nested_delimiter="__"
    )

    # Secrets stay out of repr, so a failing assert or a log line never prints them.
    supabase_db_url: str | None = Field(default=None, repr=False)
    typesafe_api_key: str | None = Field(default=None, repr=False)
    xai_api_key: str | None = Field(default=None, repr=False)
    langfuse_public_key: str | None = Field(default=None, repr=False)
    langfuse_secret_key: str | None = Field(default=None, repr=False)
    langfuse_base_url: str = "https://cloud.langfuse.com"
    cors_origins: list[str] = ["http://localhost:3000"]
    # TestClient sends Host: testserver.
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    transfer_pattern: str = "TRASPASO|TRANSFER|BIZUM|TRF"
    transfer_window_days: int = 2
    jev_concurrency: int = Field(default=8, ge=1)
    category_threshold: float = 0.95
    brand_threshold: float = 0.5
    # jev picks the right known merchant but with low confidence: 0.5 cuts duplicates by 40% with
    # no new wrong join (docs/evals/HISTORY.md, 2026-10-17). 0.3 to 0.5 is a /review suggestion.
    merge_threshold: float = 0.5
    merge_suggestion_floor: float = 0.3
    subscription_threshold: float = 0.7
    chat: ChatSettings = ChatSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
