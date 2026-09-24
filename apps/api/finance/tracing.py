"""Langfuse client configured from the repo-root .env (the SDK reads LANGFUSE_* variables)."""

import os
from functools import lru_cache

from langfuse import Langfuse, get_client

from finance.settings import get_settings


@lru_cache
def langfuse() -> Langfuse:
    """Without keys the SDK logs one warning and returns a client that records nothing."""
    settings = get_settings()
    values = {
        "LANGFUSE_PUBLIC_KEY": settings.langfuse_public_key,
        "LANGFUSE_SECRET_KEY": settings.langfuse_secret_key,
        "LANGFUSE_BASE_URL": settings.langfuse_base_url,
    }
    for name, value in values.items():
        if value:
            os.environ.setdefault(name, value)
    return get_client()
