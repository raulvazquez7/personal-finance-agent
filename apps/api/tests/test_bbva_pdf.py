from datetime import date
from decimal import Decimal

import pytest

from finance.ingestion.adapters.bbva_pdf import BbvaPdfAdapter, parse_pages

PAGE_1 = """EXTRACTO MENSUAL DE CUENTAS PERSONALES
EXTRACTO DE ENERO 2026 Fecha de emisión: 01/02/2026
IBAN ES91 0182 0418 4502 0005 1332 BIC: HOJA 001
Titulares: JANE DOE
F.Oper. F.Valor Concepto Importe Saldo
SALDO ANTERIOR - - - - - - - - - - - 559,16
02/01 30/12 PAGO CON TARJETA EN SUPERMERCADOS -6,00 553,16
4931000000000000 NOOR ALIMENTACION VILADECANS ES
20/01 18/01 BIZUM 500,00 1.053,16
RECIBIDO:Jane
Todos los importes de este extracto se expresan en: SALDO A NUESTRO FAVOR SALDO A SU FAVOR
EURO 1.053,16
"""

PAGE_2 = """EXTRACTO DE ENERO 2026 HOJA 002
F.Oper. F.Valor Concepto Importe Saldo
31/01 31/01 CARGO POR AMORTIZACION DE PRESTAMO/CREDITO -198,40 854,76
0182-3974-65-0000000000
Todos los importes de este extracto se expresan en: SALDO A NUESTRO FAVOR SALDO A SU FAVOR
EURO 854,76
"""


def test_header_gives_iban_and_statement_month():
    header = parse_pages([PAGE_1, PAGE_2]).header
    assert header.bank == "bbva"
    assert header.iban == "ES9101820418450200051332"
    assert header.period_start == date(2026, 1, 1)
    assert header.period_end == date(2026, 1, 31)


def test_rows_across_pages_with_detail_lines():
    rows = parse_pages([PAGE_1, PAGE_2]).transactions
    assert len(rows) == 3
    first, bizum, loan = rows
    assert first.booked_at == date(2026, 1, 2)
    assert first.value_date == date(2025, 12, 30)  # December value date in a January statement
    assert first.amount == Decimal("-6.00")
    assert first.balance_after == Decimal("553.16")
    assert first.description_raw == (
        "PAGO CON TARJETA EN SUPERMERCADOS | 4931000000000000 NOOR ALIMENTACION VILADECANS ES"
    )
    assert first.merchant == "NOOR ALIMENTACION VILADECANS ES"
    assert bizum.amount == Decimal("500.00")
    assert bizum.merchant == "RECIBIDO:JANE"
    assert loan.amount == Decimal("-198.40")
    assert loan.merchant is None


def test_footer_totals_are_not_rows():
    rows = parse_pages([PAGE_1]).transactions
    assert all(row.description_raw.startswith(("PAGO", "BIZUM")) for row in rows)


def test_missing_header_fails_loudly():
    with pytest.raises(ValueError, match="BBVA"):
        parse_pages(["F.Oper. F.Valor Concepto Importe Saldo\n01/01 01/01 X -1,00 1,00\n"])


def test_sniff_recognises_first_page_regardless_of_spacing():
    adapter = BbvaPdfAdapter()
    assert adapter.sniff(PAGE_1)
    assert adapter.sniff(PAGE_1.replace(" ", ""))
    assert not adapter.sniff("Concepto Fecha Importe Saldo\nPeriodo 01/06/2026 - 05/08/2026")


PAGE_OVERDRAWN = """EXTRACTO DE ENERO 2026 HOJA 001
IBAN ES91 0182 0418 4502 0005 1332 BIC: HOJA 001
F.Oper. F.Valor Concepto Importe Saldo
02/01 02/01 COMISION DESCUBIERTO -50,00 -45,30
"""


def test_row_with_negative_balance_is_kept():
    rows = parse_pages([PAGE_OVERDRAWN]).transactions
    assert len(rows) == 1  # an overdrawn balance must not silently drop the row
    assert rows[0].amount == Decimal("-50.00")
    assert rows[0].balance_after == Decimal("-45.30")


PAGE_DECEMBER = """EXTRACTO MENSUAL DE CUENTAS PERSONALES
EXTRACTO DE DICIEMBRE 2025 Fecha de emisión: 01/01/2026
IBAN ES91 0182 0418 4502 0005 1332 BIC: HOJA 001
Titulares: JANE DOE
F.Oper. F.Valor Concepto Importe Saldo
31/12 02/01 COMPRA NAVIDAD -50,00 100,00
4931000000000000 REGALOS JANE VILADECANS ES
Todos los importes de este extracto se expresan en: SALDO A NUESTRO FAVOR SALDO A SU FAVOR
EURO 100,00
"""


def test_january_value_date_in_a_december_statement_rolls_forward():
    (row,) = parse_pages([PAGE_DECEMBER]).transactions
    assert row.booked_at == date(2025, 12, 31)
    assert row.value_date == date(2026, 1, 2)  # January value date in a December statement
