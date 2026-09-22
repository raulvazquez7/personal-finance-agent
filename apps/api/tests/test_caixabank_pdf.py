from datetime import date
from decimal import Decimal

import pytest

from finance.ingestion.adapters.caixabank_pdf import CaixaBankPdfAdapter, parse_text

SAMPLE = """1/1
Titular JANE DOE IBAN ES91 2100 0418 4502 0005 1332
Periodo 01/06/2026 - 05/08/2026 Saldo disponible
Concepto Fecha Importe Saldo
AIRBNB * ABC123 05/08/2026 -292,77€ 1.774,02€
NOMINA (TRF) 03/08/2026 +2326,31€2.066,79€
MERCADONA 3087 L 28/07/2026 -76,59€ 1.133,47€
0182-8582-97-0830 08/06/2026 -310,96€ 37.672,44€
"""


def test_header_is_parsed():
    statement = parse_text(SAMPLE)
    assert statement.header.bank == "caixabank"
    assert statement.header.iban == "ES9121000418450200051332"
    assert statement.header.period_start == date(2026, 6, 1)
    assert statement.header.period_end == date(2026, 8, 5)


def test_rows_are_parsed_including_glued_amount_and_balance():
    rows = parse_text(SAMPLE).transactions
    assert len(rows) == 4
    assert rows[0].booked_at == date(2026, 8, 5)
    assert rows[0].amount == Decimal("-292.77")
    assert rows[0].balance_after == Decimal("1774.02")
    assert rows[0].description_raw == "AIRBNB * ABC123"
    assert rows[1].amount == Decimal("2326.31")
    assert rows[1].balance_after == Decimal("2066.79")
    assert rows[2].merchant == "MERCADONA 3087 L"
    assert rows[3].merchant is None  # account reference, not a merchant


def test_missing_header_fails_loudly():
    with pytest.raises(ValueError, match="CaixaBank"):
        parse_text("Concepto Fecha Importe Saldo\nX 01/01/2026 -1,00€ 1,00€\n")


def test_sniff_recognises_first_page_regardless_of_spacing():
    adapter = CaixaBankPdfAdapter()
    assert adapter.sniff(SAMPLE)
    assert adapter.sniff(SAMPLE.replace(" ", ""))
    assert not adapter.sniff("EXTRACTO DE JULIO 2026\nF.Oper. F.Valor Concepto Importe Saldo")
