"""One loan = one merchant: the contract number on its bank lines names it (spec 2.3)."""

import re

from psycopg import Connection

from finance.categorization.labels import get_or_create_merchant

# BBVA prints a loan's contract number like an account number: 4-4-2-10 digits.
CONTRACT = re.compile(r"\b\d{4}-\d{4}-\d{2}-\d{10}\b")
LOAN_SLUGS = ["loan_received", "loan_payment"]


def loan_merchant_name(description_raw: str) -> str | None:
    match = CONTRACT.search(description_raw)
    return f"Loan ····{match.group()[-4:]}" if match else None


def link_loans(conn: Connection) -> int:
    """Give every loan row without a merchant the merchant of its contract. A row of the same
    contract already linked by this step wins, so a loan the user renamed keeps its new
    instalments."""
    rows = conn.execute(
        "select id, description_raw from transactions"
        " where category_slug = any(%s) and merchant_id is null",
        (LOAN_SLUGS,),
    ).fetchall()
    linked = 0
    for row in rows:
        match = CONTRACT.search(row["description_raw"])
        if match is None:
            continue
        known = conn.execute(
            "select merchant_id from transactions where merchant_id is not null"
            " and merchant_source = 'rule' and category_slug = any(%s)"
            " and strpos(description_raw, %s) > 0 limit 1",
            (LOAN_SLUGS, match.group()),
        ).fetchone()
        merchant_id = (
            known["merchant_id"]
            if known
            else get_or_create_merchant(conn, loan_merchant_name(row["description_raw"]))
        )
        conn.execute(
            "update transactions set merchant_id = %s, merchant_source = 'rule', updated_at = now()"
            " where id = %s",
            (merchant_id, row["id"]),
        )
        linked += 1
    return linked
