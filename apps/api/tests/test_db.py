import pytest

from finance.db import connection

pytestmark = pytest.mark.integration

EXPECTED_COLUMNS: dict[str, set[str]] = {
    "accounts": {"id", "bank", "iban", "name", "currency", "created_at"},
    "imports": {
        "id",
        "account_id",
        "filename",
        "file_sha256",
        "period_start",
        "period_end",
        "rows_total",
        "rows_new",
        "rows_duplicate",
        "imported_at",
    },
    "transactions": {
        "id",
        "account_id",
        "import_id",
        "booked_at",
        "value_date",
        "amount",
        "currency",
        "description_raw",
        "merchant",
        "balance_after",
        "dedup_key",
        "tx_type",
        "category_slug",
        "category_source",
        "category_confidence",
        "jev_suggestions",
        "is_subscription",
        "transfer_pair_id",
        "needs_review",
        "created_at",
        "updated_at",
    },
}

# The importer relies on these for `on conflict` upserts.
EXPECTED_UNIQUE_COLUMNS = {("accounts", "iban"), ("transactions", "dedup_key")}


def test_migration_created_ledger_tables():
    with connection() as conn:
        rows = conn.execute(
            "select table_name from information_schema.tables where table_schema = 'public'"
        ).fetchall()
    names = {row["table_name"] for row in rows}
    assert set(EXPECTED_COLUMNS) <= names


def test_ledger_tables_have_the_expected_columns():
    with connection() as conn:
        rows = conn.execute(
            "select table_name, column_name from information_schema.columns"
            " where table_schema = 'public' and table_name = any(%s)",
            (sorted(EXPECTED_COLUMNS),),
        ).fetchall()
    columns: dict[str, set[str]] = {table: set() for table in EXPECTED_COLUMNS}
    for row in rows:
        columns[row["table_name"]].add(row["column_name"])
    assert columns == EXPECTED_COLUMNS


def test_unique_constraints_backing_on_conflict_exist():
    with connection() as conn:
        rows = conn.execute(
            "select tc.table_name, kcu.column_name"
            " from information_schema.table_constraints tc"
            " join information_schema.key_column_usage kcu"
            "   on kcu.constraint_name = tc.constraint_name"
            "  and kcu.table_schema = tc.table_schema"
            " where tc.constraint_type = 'UNIQUE' and tc.table_schema = 'public'"
        ).fetchall()
    unique_columns = {(row["table_name"], row["column_name"]) for row in rows}
    assert EXPECTED_UNIQUE_COLUMNS <= unique_columns
