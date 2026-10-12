import asyncio

import pytest
from psycopg import errors

from finance.agent.sql_runner import agent_session, explain, run_query
from finance.db import async_pool

pytestmark = pytest.mark.integration


def _run(sql: str, row_limit: int = 200):
    async def go():
        async with async_pool() as pool:
            return await run_query(pool, sql, row_limit=row_limit, timeout_seconds=10)

    return asyncio.run(go())


def test_a_query_over_the_agent_views_returns_columns_and_plain_rows():
    result = _run("SELECT 'x' AS label, 2.50::numeric AS amount, DATE '1999-01-31' AS day")
    assert (result.columns, result.rows) == (
        ["label", "amount", "day"],
        [["x", "2.50", "1999-01-31"]],
    )
    assert (result.row_count, result.truncated, result.error) == (1, False, None)


def test_rows_beyond_the_limit_are_cut_and_flagged():
    result = _run("SELECT n FROM generate_series(1, 5) AS n ORDER BY n", row_limit=3)
    assert result.rows == [["1"], ["2"], ["3"]] and result.truncated


def test_a_rejected_query_never_reaches_the_database():
    result = _run("DELETE FROM transactions")
    assert result.error == "DELETE is not a SELECT" and result.hint


def test_agent_reader_cannot_read_base_tables_even_past_the_guard():
    async def go():
        async with async_pool() as pool, agent_session(pool, 10) as conn:
            await conn.execute("SELECT count(*) FROM public.transactions")

    with pytest.raises(errors.InsufficientPrivilege):
        asyncio.run(go())


def test_the_transaction_refuses_writes_even_after_a_role_escape():
    async def go():
        async with async_pool() as pool, agent_session(pool, 10) as conn:
            await conn.execute("SELECT set_config('role', 'postgres', true)")
            await conn.execute("INSERT INTO public.chat_threads (title) VALUES ('ZZTEST')")

    with pytest.raises(errors.ReadOnlySqlTransaction):
        asyncio.run(go())


def test_explain_reports_the_first_error_line():
    async def go():
        async with async_pool() as pool:
            return await explain(pool, "SELECT nope FROM transactions"), await explain(
                pool, "SELECT count(*) FROM transactions"
            )

    broken, fine = asyncio.run(go())
    assert broken == 'column "nope" does not exist' and fine is None


def test_columns_with_the_same_name_are_all_kept():
    result = _run("SELECT 1 AS n, 2 AS n")
    assert (result.columns, result.rows) == (["n", "n"], [["1", "2"]])


def test_a_query_ending_in_a_line_comment_still_runs():
    result = _run("SELECT 1 AS n -- a note")
    assert (result.rows, result.error) == ([["1"]], None)


def test_a_function_that_runs_sql_from_a_string_never_reaches_the_database():
    """query_to_xml runs its text as SQL, where set_config can reset the role to the session
    user: the guard must reject it before it runs."""
    result = _run(
        "SELECT query_to_xml('select set_config(''role'',''none'',true)', true, false, '') AS a, "
        "query_to_xml('select current_user', true, false, '') AS b"
    )
    assert result.error == "function query_to_xml is not allowed: only standard SQL functions are"
    assert result.rows == [] and result.columns == [] and not result.infra_error


def test_the_agent_session_runs_as_agent_reader():
    async def go():
        async with async_pool() as pool, agent_session(pool, 10) as conn:
            cursor = await conn.execute("SELECT current_user AS name")
            return await cursor.fetchone()

    assert asyncio.run(go())["name"] == "agent_reader"
