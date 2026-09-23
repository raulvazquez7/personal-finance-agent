from datetime import date
from decimal import Decimal

import pytest

from finance.ingestion.normalize import normalize_merchant, parse_amount_es, parse_date_es


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.756,67", Decimal("1756.67")),
        ("-6,00", Decimal("-6.00")),
        ("+2326,31€", Decimal("2326.31")),
        ("38.066,79€", Decimal("38066.79")),
        ("500,00", Decimal("500.00")),
    ],
)
def test_parse_amount_es(text, expected):
    assert parse_amount_es(text) == expected


def test_parse_date_es_full():
    assert parse_date_es("05/08/2026") == date(2026, 8, 5)


def test_parse_date_es_day_month_with_year():
    assert parse_date_es("29/06", year=2026) == date(2026, 6, 29)


def test_parse_date_es_day_month_without_year_fails():
    with pytest.raises(ValueError):
        parse_date_es("29/06")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("4931000000000000 TECNOTRON SAU - PV-00860", "TECNOTRON SAU - PV-00860"),
        ("N1234567890 UNION DE CREDITOS INMOBILIARIOS", "UNION DE CREDITOS INMOBILIARIOS"),
        ("4931000000000000", None),
        ("0182-3974-65-0000000000", None),
        ("RECIBIDO:Jane", "RECIBIDO:JANE"),
        ("MERCADONA   3087 L", "MERCADONA 3087 L"),
        ("", None),
    ],
)
def test_normalize_merchant(text, expected):
    assert normalize_merchant(text) == expected
