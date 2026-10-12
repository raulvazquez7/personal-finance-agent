import pytest
from pydantic import ValidationError

from finance.settings import Settings

SECRETS = (
    "supabase_db_url",
    "typesafe_api_key",
    "xai_api_key",
    "langfuse_public_key",
    "langfuse_secret_key",
)


def test_repr_never_shows_secrets():
    # No .env: a failing assert must never print the developer's real keys.
    settings = Settings(_env_file=None, **{name: f"fake-{name}" for name in SECRETS})
    shown = repr(settings)
    assert [name for name in SECRETS if f"fake-{name}" in shown] == []


def test_jev_concurrency_below_one_is_rejected():
    # A semaphore of 0 would wait forever for the first jev call.
    with pytest.raises(ValidationError, match="jev_concurrency"):
        Settings(_env_file=None, jev_concurrency=0)


def test_chat_defaults_follow_the_spec():
    chat = Settings(_env_file=None).chat
    assert (chat.model, chat.reasoning_effort) == ("xai:grok-4.7", "high")
    assert (chat.summary_model, chat.summary_reasoning_effort) == ("xai:grok-4.7", "medium")
    assert chat.title_model == "xai:grok-4.20-non-reasoning"
    assert chat.summary_trigger_tokens == 150_000
    assert chat.pool_timeout_seconds == 5


def test_chat_settings_come_from_nested_env_variables(monkeypatch):
    monkeypatch.setenv("CHAT__REASONING_EFFORT", "medium")
    monkeypatch.setenv("CHAT__MAX_SQL_CALLS_PER_TURN", "5")
    chat = Settings(_env_file=None).chat
    assert (chat.reasoning_effort, chat.max_sql_calls_per_turn) == ("medium", 5)


def test_an_unknown_reasoning_effort_is_rejected():
    with pytest.raises(ValidationError, match="reasoning_effort"):
        Settings(_env_file=None, chat={"reasoning_effort": "extreme"})


def test_model_calls_must_leave_room_for_the_answer():
    # With as many model calls as queries, the last query's result would never be answered.
    with pytest.raises(ValidationError, match="max_model_calls_per_turn"):
        Settings(_env_file=None, chat={"max_sql_calls_per_turn": 8, "max_model_calls_per_turn": 8})
