from datetime import date

import pytest
from fastapi.testclient import TestClient

from finance.api.deps import db
from finance.api.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
def client(db_conn):
    previous = app.dependency_overrides.get(db)
    app.dependency_overrides[db] = lambda: db_conn
    yield TestClient(app)
    if previous is None:
        app.dependency_overrides.pop(db, None)
    else:
        app.dependency_overrides[db] = previous


def _account(conn, iban: str, name: str):
    return conn.execute(
        "insert into accounts (bank, iban, name) values ('bbva', %s, %s) returning id", (iban, name)
    ).fetchone()["id"]


def _import(conn, account, start: date | None, end: date | None, imported_at: str):
    return conn.execute(
        "insert into imports (account_id, filename, file_sha256, period_start, period_end,"
        " rows_total, imported_at) values (%s, 'zztest.pdf', 'x', %s, %s, 1, %s) returning id",
        (account, start, end, imported_at),
    ).fetchone()["id"]


def test_imports_list_newest_statement_first_then_account_then_null_periods(client, db_conn):
    savings = _account(db_conn, "ES0000000000000000000091", "ZZTEST savings")
    everyday = _account(db_conn, "ES0000000000000000000092", "ZZTEST everyday")
    january = _import(
        db_conn, everyday, date(1999, 1, 1), date(1999, 1, 31), "1999-03-01T10:00:00Z"
    )
    february_savings = _import(
        db_conn, savings, date(1999, 2, 1), date(1999, 2, 28), "1999-03-01T10:00:00Z"
    )
    february = _import(
        db_conn, everyday, date(1999, 2, 1), date(1999, 2, 28), "1999-03-01T09:00:00Z"
    )
    february_again = _import(
        db_conn, everyday, date(1999, 2, 1), date(1999, 2, 28), "1999-03-02T09:00:00Z"
    )
    undated = _import(db_conn, everyday, None, None, "1999-03-03T10:00:00Z")

    body = client.get("/imports").json()

    ours = [row["id"] for row in body if row["account_id"] in {str(savings), str(everyday)}]
    assert ours == [
        str(february_again),
        str(february),
        str(february_savings),
        str(january),
        str(undated),
    ]
    # Null periods come after every dated import, ours or not.
    first_null = next(index for index, row in enumerate(body) if row["period_end"] is None)
    assert all(row["period_end"] is None for row in body[first_null:])
