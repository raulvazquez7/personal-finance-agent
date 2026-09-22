"""Postgres access: one process-level pool, dict rows, plain SQL."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from finance.settings import get_settings


@lru_cache
def get_pool() -> ConnectionPool:
    url = get_settings().supabase_db_url
    if not url:
        raise RuntimeError("SUPABASE_DB_URL is not set; see .env.example")
    return ConnectionPool(url, min_size=1, max_size=5, kwargs={"row_factory": dict_row}, open=True)


@contextmanager
def connection() -> Iterator[Connection]:
    with get_pool().connection() as conn:
        yield conn
