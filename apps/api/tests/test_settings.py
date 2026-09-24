import pytest
from pydantic import ValidationError

from finance.settings import Settings

SECRETS = (
    "supabase_db_url",
    "supabase_db_url_readonly",
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
