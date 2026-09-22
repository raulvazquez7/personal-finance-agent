import pytest

from finance.db import connection

pytestmark = pytest.mark.integration


def test_migration_created_ledger_tables():
    with connection() as conn:
        rows = conn.execute(
            "select table_name from information_schema.tables where table_schema = 'public'"
        ).fetchall()
    names = {row["table_name"] for row in rows}
    assert {"accounts", "imports", "transactions"} <= names
