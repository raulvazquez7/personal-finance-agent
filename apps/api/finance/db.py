"""Postgres access: one process-level pool, dict rows, plain SQL."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from functools import lru_cache

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, ConnectionPool

from finance.settings import get_settings


def _database_url() -> str:
    url = get_settings().supabase_db_url
    if not url:
        raise RuntimeError("SUPABASE_DB_URL is not set; see .env.example")
    return url


@lru_cache
def get_pool() -> ConnectionPool:
    return ConnectionPool(
        _database_url(), min_size=1, max_size=5, kwargs={"row_factory": dict_row}, open=True
    )


@contextmanager
def connection() -> Iterator[Connection]:
    with get_pool().connection() as conn:
        yield conn


@asynccontextmanager
async def async_pool(
    max_size: int = 5, timeout: float = 30.0
) -> AsyncIterator[AsyncConnectionPool]:
    """The chat's async pool, bound to the running event loop. LangGraph's checkpointer needs
    autocommit, dict rows and prepare_threshold=0; the agent's queries open explicit transactions.
    `timeout` is how long a caller waits for a connection (psycopg_pool's default is 30 s).
    """
    pool = AsyncConnectionPool(
        _database_url(),
        open=False,
        max_size=max_size,
        timeout=timeout,
        kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0},
    )
    await pool.open()
    try:
        yield pool
    finally:
        await pool.close()
