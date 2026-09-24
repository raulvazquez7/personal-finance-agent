"""The slice-2 schema is applied and no card number survives outside description_raw."""

from pathlib import Path
from uuid import uuid4

import pytest

from finance.db import connection

pytestmark = pytest.mark.integration

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "20260924000000_categorization.sql"
)

# (bank, description_raw, merchant as slice 1 stored it) -> (bank_concept, merchant, card_last4)
BACKFILL_CASES = [
    (
        ("bbva", "PAGO CON TARJETA | 1111222233334444 ACME SHOP", "ACME SHOP 1111222233334444"),
        ("PAGO CON TARJETA", "ACME SHOP", "4444"),
    ),
    (
        ("bbva", "PAGO CON TARJETA | 5555666677778888 FAKE CAFE", "FAKE CAFE"),
        ("PAGO CON TARJETA", "FAKE CAFE", "8888"),
    ),
    (
        ("bbva", "PAGO CON TARJETA | 9999000011112222", "9999000011112222"),
        ("PAGO CON TARJETA", None, "2222"),
    ),
    (("bbva", "CUOTA MENSUAL", None), ("CUOTA MENSUAL", None, None)),
    (
        ("bbva", "PAGO CON TARJETA 1111222233334444 ACME", None),
        ("PAGO CON TARJETA ACME", None, "4444"),
    ),
    (
        ("bbva", "TRANSFERENCIA | REF 12345678901234567890", "REF 12345678901234567890"),
        ("TRANSFERENCIA", "REF 12345678901234567890", None),
    ),
    (("caixabank", "BIZUM ENVIADO", "BIZUM ENVIADO"), (None, "BIZUM ENVIADO", None)),
]


def _columns(conn, table: str) -> set[str]:
    rows = conn.execute(
        "select column_name from information_schema.columns where table_name = %s", (table,)
    ).fetchall()
    return {row["column_name"] for row in rows}


def _backfill_sql() -> str:
    """The migration's backfill section, rerun on synthetic rows (it is idempotent)."""
    sql = MIGRATION.read_text()
    return sql[sql.index("-- Backfill") :]


def _insert_slice_1_row(conn, bank: str, description_raw: str, merchant: str | None):
    account = conn.execute(
        "insert into accounts (bank, iban, name) values (%s, %s, 'test')"
        " on conflict (iban) do update set name = excluded.name returning id",
        (bank, f"XX00TEST{bank.upper()}"),
    ).fetchone()["id"]
    import_id = conn.execute(
        "insert into imports (account_id, filename, file_sha256, rows_total)"
        " values (%s, 'test.pdf', 'x', 1) returning id",
        (account,),
    ).fetchone()["id"]
    return conn.execute(
        "insert into transactions (account_id, import_id, booked_at, amount, description_raw,"
        " merchant, dedup_key, tx_type)"
        " values (%s, %s, '2026-07-01', -1, %s, %s, %s, 'expense') returning id",
        (account, import_id, description_raw, merchant, uuid4().hex),
    ).fetchone()["id"]


def test_categorization_tables_exist():
    with connection() as conn:
        assert {"slug", "tx_type", "level1", "what", "not_for"} <= _columns(conn, "categories")
        assert {"match_key", "confirmed", "merge_candidate_id"} <= _columns(conn, "merchants")
        assert {"match_field", "pattern", "direction"} <= _columns(conn, "rules")
        assert {"source", "model", "is_subscription"} <= _columns(conn, "transaction_labels")


def test_transactions_gain_categorization_columns():
    with connection() as conn:
        columns = _columns(conn, "transactions")
    assert {"bank_concept", "card_last4", "merchant_id", "category_probabilities"} <= columns
    assert "jev_suggestions" not in columns


def test_no_card_number_in_merchant_or_bank_concept():
    with connection() as conn:
        row = conn.execute(
            r"select count(*) as n from transactions"
            r" where merchant ~ '\m\d{12,19}\M' or bank_concept ~ '\m\d{12,19}\M'"
        ).fetchone()
    assert row["n"] == 0


def test_backfill_structures_slice_1_rows():
    with connection() as conn, conn.transaction(force_rollback=True):
        ids = [_insert_slice_1_row(conn, *row) for row, _ in BACKFILL_CASES]
        conn.execute(_backfill_sql())
        rows = conn.execute(
            "select id, bank_concept, merchant, card_last4 from transactions where id = any(%s)",
            (ids,),
        ).fetchall()
    got = {row["id"]: (row["bank_concept"], row["merchant"], row["card_last4"]) for row in rows}
    assert [got[tx_id] for tx_id in ids] == [expected for _, expected in BACKFILL_CASES]
