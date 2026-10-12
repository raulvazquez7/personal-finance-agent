from datetime import date
from decimal import Decimal

import psycopg
import pytest
from psycopg import errors
from psycopg_pool import PoolTimeout

from finance.agent.sql_runner import cell, failed


def test_cells_read_as_plain_text():
    assert [cell(v) for v in (Decimal("1234.50"), date(2026, 7, 1), True, None, 3)] == [
        "1234.50",
        "2026-07-01",
        "true",
        None,
        "3",
    ]


def test_sql_mistakes_come_back_with_a_hint_for_the_model():
    result = failed("SELECT x", errors.UndefinedColumn('column "merchnt" does not exist'), 10)
    assert result.error == 'column "merchnt" does not exist'
    assert result.hint == "Use only the columns listed for that view in the data model."
    assert not result.infra_error


def test_a_division_by_zero_gets_its_own_hint_before_the_generic_data_error():
    result = failed("SELECT 1/0", errors.DivisionByZero("division by zero"), 10)
    assert result.hint == "Protect divisions with NULLIF(denominator, 0)."


@pytest.mark.parametrize(
    ("kind", "hint"),
    [
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
    ],
)
def test_each_postgres_error_class_gets_its_hint(kind, hint):
    result = failed("SELECT 1", kind("some error"), 10)
    assert result.hint == hint and not result.infra_error


def test_a_timeout_asks_for_a_lighter_query():
    result = failed("SELECT 1", errors.QueryCanceled("canceling statement"), 10)
    assert result.error == "the query took longer than 10 s"
    assert not result.infra_error


def test_an_unreachable_database_is_an_infrastructure_failure():
    for error in (psycopg.OperationalError("connection refused"), PoolTimeout("no connection")):
        result = failed("SELECT 1", error, 10)
        assert result.infra_error and result.hint is None
