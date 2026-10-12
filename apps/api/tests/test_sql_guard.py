import pytest

from finance.agent.sql_guard import RejectedQuery, check_query

ALLOWED = [
    "SELECT month, SUM(spend) FROM transactions GROUP BY month",
    "select merchant from transactions where note ilike '%drop%' limit 20",
    "WITH m AS (SELECT month, SUM(spend) AS s FROM transactions GROUP BY 1) SELECT * FROM m",
    "SELECT 1 UNION ALL SELECT 2",
    "SELECT merchant, string_agg(DISTINCT note, ' | ') FROM transactions GROUP BY 1",
    "SELECT m FROM generate_series(DATE '2026-01-01', DATE '2026-03-01', INTERVAL '1 month') AS m",
    "SELECT t.merchant FROM transactions t JOIN subscriptions s ON s.merchant = t.merchant",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_reads_over_the_agent_views_pass(sql):
    assert check_query(sql) == sql


def test_trailing_semicolons_and_spaces_are_dropped():
    assert check_query("  SELECT * FROM subscriptions WHERE active;; ") == (
        "SELECT * FROM subscriptions WHERE active"
    )


REJECTED = [
    ("WITH d AS (DELETE FROM transactions RETURNING *) SELECT * FROM d", "DELETE is not allowed"),
    ("UPDATE transactions SET note = 'x'", "UPDATE is not a SELECT"),
    ("SELECT 1; SELECT 2", "found 2 statements"),
    ("SELECT * FROM public.transactions", "unknown table"),
    ("SELECT * FROM accounts", "unknown table"),
    ("SELECT * FROM information_schema.tables", "unknown table"),
    ("SELECT set_config('role', 'postgres', true)", "function set_config"),
    ("SELECT pg_sleep(5)", "function pg_sleep"),
    ("SELECT * FROM dblink('x', 'select 1') AS t(a int)", "function dblink"),
    ("SELECT * FROM transactions FOR UPDATE", "LOCK is not allowed"),
    ("SET ROLE postgres", "COMMAND is not a SELECT"),
    ("COPY transactions TO STDOUT", "COPY is not a SELECT"),
    ("SELECT * FROM (", "does not parse"),
]


@pytest.mark.parametrize(("sql", "reason"), REJECTED)
def test_anything_but_one_read_is_rejected_with_a_hint(sql, reason):
    with pytest.raises(RejectedQuery) as raised:
        check_query(sql)
    assert reason in raised.value.reason
    assert raised.value.hint
