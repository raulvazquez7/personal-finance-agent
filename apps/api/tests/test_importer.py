from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from finance.db import connection
from finance.ingestion.importer import import_statement, transaction_rows
from finance.models import NormalizedTransaction, ParsedStatement, StatementHeader


def _statement() -> ParsedStatement:
    header = StatementHeader(bank="bbva", iban="ES9101820418450200051332")
    coffee = NormalizedTransaction(
        booked_at=date(2026, 7, 1),
        amount=Decimal("-1.50"),
        description_raw="COFFEE",
        balance_after=Decimal("10"),
    )
    salary = NormalizedTransaction(
        booked_at=date(2026, 7, 2),
        amount=Decimal("2000"),
        description_raw="SALARY",
        balance_after=Decimal("2010"),
    )
    return ParsedStatement(header=header, transactions=[coffee, coffee, salary])


def test_transaction_rows_carry_unique_keys_and_sign_based_type():
    rows = transaction_rows(_statement(), uuid4(), uuid4())
    keys = [row[9] for row in rows]
    types = [row[10] for row in rows]
    assert len(set(keys)) == 3
    assert types == ["expense", "expense", "income"]


def test_transaction_rows_carry_concept_and_card_last4():
    header = StatementHeader(bank="bbva", iban="ES9101820418450200051332")
    card = NormalizedTransaction(
        booked_at=date(2026, 7, 3),
        amount=Decimal("-9.90"),
        description_raw="PAGO CON TARJETA EN SUPERMERCADOS | 1234567812345678 SUPER ACME",
        merchant="1234567812345678 SUPER ACME",
        balance_after=Decimal("5"),
    )
    row = transaction_rows(ParsedStatement(header=header, transactions=[card]), uuid4(), uuid4())[0]
    assert row[7] == "SUPER ACME"
    assert row[11] == "PAGO CON TARJETA EN SUPERMERCADOS"
    assert row[12] == "5678"


# Real statements: exact row counts of the three sample files on Raul's machine.
EXPECTED_ROWS = {
    "bbva_extracto_julio_01.pdf": 78,
    "bbva_extracto_julio_02.pdf": 97,
    "caixa_extracto.pdf": 76,
}


@pytest.mark.integration
def test_real_statements_import_once_and_never_twice(raw_pdfs):
    for path in raw_pdfs:
        if path.name not in EXPECTED_ROWS:
            continue
        with connection() as conn, conn.transaction(force_rollback=True):
            first = import_statement(path.read_bytes(), path.name, conn)
            second = import_statement(path.read_bytes(), path.name, conn)
        assert first.rows_total == EXPECTED_ROWS[path.name]
        assert second.rows_total == first.rows_total
        assert second.rows_new == 0
        assert second.rows_duplicate == first.rows_total
