"""Import one PDF statement: detect bank, resolve account by IBAN, insert without duplicates."""

import hashlib
from uuid import UUID

from psycopg import Connection

from finance.ingestion.adapters import detect_adapter
from finance.ingestion.dedup import dedup_key, occurrence_indexes
from finance.models import ImportSummary, ParsedStatement

_INSERT_TRANSACTION = """
insert into transactions (account_id, import_id, booked_at, value_date, amount, currency,
                          description_raw, merchant, balance_after, dedup_key, tx_type)
values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
on conflict (dedup_key) do nothing
"""


def import_statement(pdf_bytes: bytes, filename: str, conn: Connection) -> ImportSummary:
    parsed = detect_adapter(pdf_bytes).parse(pdf_bytes)
    with conn.transaction():
        account_id = _resolve_account(conn, parsed)
        import_id = conn.execute(
            "insert into imports (account_id, filename, file_sha256, period_start, period_end,"
            " rows_total) values (%s, %s, %s, %s, %s, %s) returning id",
            (
                account_id,
                filename,
                hashlib.sha256(pdf_bytes).hexdigest(),
                parsed.header.period_start,
                parsed.header.period_end,
                len(parsed.transactions),
            ),
        ).fetchone()["id"]
        rows_new = _insert_transactions(conn, parsed, account_id, import_id)
        rows_duplicate = len(parsed.transactions) - rows_new
        conn.execute(
            "update imports set rows_new = %s, rows_duplicate = %s where id = %s",
            (rows_new, rows_duplicate, import_id),
        )
    return ImportSummary(
        import_id=import_id,
        account_id=account_id,
        bank=parsed.header.bank,
        iban_last4=parsed.header.iban[-4:],
        filename=filename,
        rows_total=len(parsed.transactions),
        rows_new=rows_new,
        rows_duplicate=rows_duplicate,
    )


def transaction_rows(parsed: ParsedStatement, account_id: UUID, import_id: UUID) -> list[tuple]:
    """Insert tuples in _INSERT_TRANSACTION column order. Pure, so it is unit-tested."""
    rows = []
    for tx, index in zip(parsed.transactions, occurrence_indexes(parsed.transactions), strict=True):
        rows.append(
            (
                account_id,
                import_id,
                tx.booked_at,
                tx.value_date,
                tx.amount,
                tx.currency,
                tx.description_raw,
                tx.merchant,
                tx.balance_after,
                dedup_key(parsed.header.iban, tx, index),
                "income" if tx.amount > 0 else "expense",
            )
        )
    return rows


def _resolve_account(conn: Connection, parsed: ParsedStatement) -> UUID:
    header = parsed.header
    existing = conn.execute("select id from accounts where iban = %s", (header.iban,)).fetchone()
    if existing:
        return existing["id"]
    created = conn.execute(
        "insert into accounts (bank, iban, name) values (%s, %s, %s) returning id",
        (header.bank, header.iban, f"{header.bank} ····{header.iban[-4:]}"),
    ).fetchone()
    return created["id"]


def _insert_transactions(
    conn: Connection, parsed: ParsedStatement, account_id: UUID, import_id: UUID
) -> int:
    inserted = 0
    with conn.cursor() as cur:
        for row in transaction_rows(parsed, account_id, import_id):
            cur.execute(_INSERT_TRANSACTION, row)
            inserted += cur.rowcount
    return inserted
