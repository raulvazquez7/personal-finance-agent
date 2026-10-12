"""Run the agent's SQL as `agent_reader`, in a read-only transaction with a timeout.

The role reads only the `agent` views; the transaction refuses any write even if the guard missed
one (slice 4 spec, section 4.2). Failures come back as data, never as exceptions, so a tool call
always gets its answer and a thread can never be left with an unanswered call.
"""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal

import psycopg
from psycopg import AsyncConnection, errors
from psycopg.rows import tuple_row
from psycopg_pool import AsyncConnectionPool, PoolTimeout

from finance.agent.models import QueryResult
from finance.agent.sql_guard import RejectedQuery, check_query

# Order matters: a subclass comes before its parent (DivisionByZero is a DataError).
_HINTS: list[tuple[type[psycopg.Error], str]] = [
    (errors.UndefinedColumn, "Use only the columns listed for that view in the data model."),
    (errors.UndefinedTable, "Read only the views transactions and subscriptions."),
    (errors.InsufficientPrivilege, "Read only the views transactions and subscriptions."),
    (
        errors.UndefinedFunction,
        "Check the function name and argument types; cast text with ::date or ::numeric.",
    ),
    (errors.GroupingError, "Every selected column that is not aggregated goes in GROUP BY."),
    (errors.SyntaxError, "Fix the syntax: write one PostgreSQL SELECT."),
    (errors.DivisionByZero, "Protect divisions with NULLIF(denominator, 0)."),
    (errors.DataError, "Check literal values and casts; dates are 'YYYY-MM-DD'."),
]


@asynccontextmanager
async def agent_session(
    pool: AsyncConnectionPool, timeout_seconds: int
) -> AsyncIterator[AsyncConnection]:
    """A connection inside a read-only transaction as agent_reader, rolled back at the end."""
    async with pool.connection() as conn, conn.transaction(force_rollback=True):
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SET LOCAL ROLE agent_reader")
        await conn.execute("SET LOCAL search_path = agent")
        await conn.execute(f"SET LOCAL statement_timeout = {int(timeout_seconds) * 1000}")
        yield conn


def cell(value: object) -> str | None:
    """A value as the model and the UI read it: plain numbers, ISO dates, empty for NULL."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date | datetime):
        return value.isoformat()
    return str(value)


def failed(sql: str, error: Exception, timeout_seconds: int) -> QueryResult:
    """The result for a query that did not run: an error the model can act on, or infra."""
    if isinstance(error, errors.QueryCanceled):
        return QueryResult(
            sql=sql,
            error=f"the query took longer than {timeout_seconds} s",
            hint="Aggregate more or narrow the period.",
        )
    first_line = str(error).splitlines()[0] if str(error) else type(error).__name__
    if isinstance(error, psycopg.OperationalError | PoolTimeout):
        return QueryResult(sql=sql, error=first_line, infra_error=True)
    hint = next((h for kind, h in _HINTS if isinstance(error, kind)), "Try a simpler query.")
    return QueryResult(sql=sql, error=first_line, hint=hint)


async def run_query(
    pool: AsyncConnectionPool, sql: str, *, row_limit: int, timeout_seconds: int
) -> QueryResult:
    """Guard and run one query; fetch at most row_limit rows and say whether there were more."""
    started = time.perf_counter()
    try:
        cleaned = check_query(sql)
    except RejectedQuery as rejected:
        return QueryResult(sql=sql, error=rejected.reason, hint=rejected.hint)
    try:
        async with agent_session(pool, timeout_seconds) as conn:
            async with conn.cursor(row_factory=tuple_row) as cursor:
                await cursor.execute(f"SELECT * FROM ({cleaned}\n) AS result LIMIT {row_limit + 1}")
                columns = [column.name for column in cursor.description or []]
                fetched = await cursor.fetchall()
    except (psycopg.Error, PoolTimeout) as error:
        return failed(sql, error, timeout_seconds)
    rows = [[cell(value) for value in row] for row in fetched[:row_limit]]
    return QueryResult(
        sql=sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=len(fetched) > row_limit,
        duration_ms=round((time.perf_counter() - started) * 1000),
    )


async def explain(pool: AsyncConnectionPool, sql: str) -> str | None:
    """None when the SQL compiles as agent_reader, else the first line of the error."""
    try:
        async with agent_session(pool, timeout_seconds=10) as conn:
            await conn.execute(f"EXPLAIN {sql}")
    except psycopg.Error as error:
        return str(error).splitlines()[0]
    return None
