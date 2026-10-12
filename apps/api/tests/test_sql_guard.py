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
    # Functions sqlglot types pass; the allowlisted ones it does not type pass too.
    "SELECT to_char(booked_at, 'YYYY-MM'), date_trunc('month', booked_at) FROM transactions",
    "SELECT EXTRACT(YEAR FROM booked_at), ROUND(AVG(spend), 2) FROM transactions GROUP BY 1",
    "SELECT COALESCE(SUM(spend), 0), NULLIF(COUNT(*), 0) FROM transactions",
    "SELECT age(booked_at) FROM transactions",
    "SELECT make_date(2026, 1, 1)",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_reads_over_the_agent_views_pass(sql):
    assert check_query(sql) == sql


def test_trailing_semicolons_and_spaces_are_dropped():
    assert check_query("  SELECT * FROM subscriptions WHERE active;; ") == (
        "SELECT * FROM subscriptions WHERE active"
    )


def test_semicolons_separated_by_spaces_are_all_dropped():
    assert check_query("SELECT 1 ; ; ") == "SELECT 1"


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
    ("SELECT 'unterminated", "does not parse"),
    ("SELECT 1 /* open comment", "does not parse"),
    ("SELECT * INTO transactions FROM subscriptions", "INTO is not allowed"),
    # Built-ins that run SQL from a string, where set_config can reset the role.
    ("SELECT query_to_xml('select 1', true, false, '') FROM transactions", "query_to_xml"),
    ("SELECT * FROM ts_stat('select 1')", "function ts_stat"),
    ("SELECT ts_rewrite('a'::tsquery, 'select 1')", "function ts_rewrite"),
    ("SELECT QUERY_TO_XML('select 1', true, false, '')", "function query_to_xml"),
    ("SELECT * FROM transactions, LATERAL ts_stat('select 1') AS s", "function ts_stat"),
    ("SELECT * FROM transactions ORDER BY query_to_xml('select 1', true, false, '')", "to_xml"),
    ("SELECT pg_advisory_lock(1)", "function pg_advisory_lock"),
    ("SELECT current_setting('role')", "function current_setting"),
    ("SELECT pg_catalog.age(booked_at) FROM transactions", "function age has a schema"),
    ("SELECT public.lower(note) FROM transactions", "function lower has a schema"),
    ("SELECT * FROM pg_catalog.ts_stat('select 1')", "function ts_stat"),
]


@pytest.mark.parametrize(("sql", "reason"), REJECTED)
def test_anything_but_one_read_is_rejected_with_a_hint(sql, reason):
    with pytest.raises(RejectedQuery) as raised:
        check_query(sql)
    assert reason in raised.value.reason
    assert raised.value.hint


def test_an_unknown_function_is_named_with_functions_that_work():
    with pytest.raises(RejectedQuery) as raised:
        check_query("SELECT query_to_xml('select 1', true, false, '') FROM transactions")
    assert raised.value.reason == (
        "function query_to_xml is not allowed: only standard SQL functions are"
    )
    assert "SUM" in raised.value.hint and "date_trunc" in raised.value.hint
