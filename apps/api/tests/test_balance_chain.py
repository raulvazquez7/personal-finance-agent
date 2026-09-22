from datetime import date
from decimal import Decimal

import pytest

from finance.ingestion.balance_chain import check_balance_chain
from finance.models import NormalizedTransaction


def _row(day: int, amount: str, balance: str | None) -> NormalizedTransaction:
    return NormalizedTransaction(
        booked_at=date(2026, 3, day),
        amount=Decimal(amount),
        description_raw=f"ROW {day}",
        balance_after=None if balance is None else Decimal(balance),
    )


# Oldest first, as BBVA prints them: 100.00 -6.00 -> 94.00 +250.00 -> 344.00.
ASCENDING = [_row(1, "-6.00", "94.00"), _row(2, "250.00", "344.00"), _row(3, "-44.00", "300.00")]

# Newest first, as CaixaBank prints them: the same chain read up the page.
DESCENDING = list(reversed(ASCENDING))


def test_clean_ascending_statement_passes():
    check_balance_chain(ASCENDING, bank="bbva", order="ascending")


def test_clean_descending_statement_passes():
    check_balance_chain(DESCENDING, bank="caixabank", order="descending")


def test_dropped_middle_row_fails_loudly():
    with pytest.raises(ValueError, match="bbva"):
        check_balance_chain([ASCENDING[0], ASCENDING[2]], bank="bbva", order="ascending")


def test_error_names_the_row_and_both_balances():
    with pytest.raises(ValueError) as excinfo:
        check_balance_chain([ASCENDING[0], ASCENDING[2]], bank="bbva", order="ascending")
    message = str(excinfo.value)
    assert "row 1" in message
    assert "50.00" in message  # expected: 94.00 - 44.00
    assert "300.00" in message  # actual balance printed on the row
    assert "a row is missing or repeated" in message  # also fires on a row captured twice


def test_dropped_middle_row_fails_loudly_when_descending():
    with pytest.raises(ValueError, match="caixabank"):
        check_balance_chain([DESCENDING[0], DESCENDING[2]], bank="caixabank", order="descending")


def test_descending_error_reports_the_index_as_printed():
    with pytest.raises(ValueError) as excinfo:
        check_balance_chain([DESCENDING[0], DESCENDING[2]], bank="caixabank", order="descending")
    assert "row 0" in str(excinfo.value)


def test_single_row_statement_is_skipped():
    check_balance_chain([ASCENDING[0]], bank="bbva", order="ascending")


def test_empty_statement_is_skipped():
    check_balance_chain([], bank="bbva", order="ascending")


def test_missing_balance_skips_the_whole_check():
    rows = [ASCENDING[0], _row(2, "250.00", None), ASCENDING[2]]
    check_balance_chain(rows, bank="bbva", order="ascending")


def test_adapters_check_their_own_output():
    from finance.ingestion.adapters import bbva_pdf, caixabank_pdf

    broken_bbva = """EXTRACTO DE ENERO 2026 HOJA 001
IBAN ES91 0182 0418 4502 0005 1332 BIC: HOJA 001
F.Oper. F.Valor Concepto Importe Saldo
02/01 02/01 COMPRA UNO -6,00 94,00
04/01 04/01 COMPRA TRES -44,00 300,00
"""
    with pytest.raises(ValueError, match="bbva"):
        bbva_pdf.parse_pages([broken_bbva])

    broken_caixabank = """1/1
Titular JANE DOE IBAN ES91 2100 0418 4502 0005 1332
Periodo 01/01/2026 - 31/01/2026 Saldo disponible
Concepto Fecha Importe Saldo
COMPRA TRES 04/01/2026 -44,00€ 300,00€
COMPRA UNO 02/01/2026 -6,00€ 94,00€
"""
    with pytest.raises(ValueError, match="caixabank"):
        caixabank_pdf.parse_text(broken_caixabank)
