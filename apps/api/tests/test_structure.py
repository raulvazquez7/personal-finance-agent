import pytest

from finance.ingestion.adapters.bbva_pdf import parse_pages
from finance.ingestion.structure import structure
from tests.test_schema import BACKFILL_CASES

BBVA_CARD_PAGE = """EXTRACTO DE JULIO 2026
IBAN ES91 0182 0418 4502 0005 1332
03/07 03/07 PAGO CON TARJETA EN SUPERMERCADOS -9,90 90,10
1234567812345678 SUPER ACME 0042 L
"""


def test_bbva_concept_is_split_and_card_number_removed():
    result = structure(
        "bbva",
        "PAGO CON TARJETA EN SUPERMERCADOS | 1234567812345678 SUPER ACME 0042",
        "SUPER ACME 1234567812345678 0042",
    )
    assert result.bank_concept == "PAGO CON TARJETA EN SUPERMERCADOS"
    assert result.merchant == "SUPER ACME 0042"
    assert result.card_last4 == "5678"


def test_caixabank_has_no_concept():
    result = structure("caixabank", "BIZUM ENVIADO", "BIZUM ENVIADO")
    assert result.bank_concept is None
    assert result.merchant == "BIZUM ENVIADO"
    assert result.card_last4 is None


def test_merchant_made_only_of_a_card_number_becomes_empty():
    assert structure("bbva", "X | 1234567812345678", "1234567812345678").merchant is None


def test_short_numbers_are_not_card_numbers():
    assert structure("bbva", "X | ACME 0042", "ACME 0042").merchant == "ACME 0042"


def test_card_last4_comes_from_the_line_when_the_adapter_already_dropped_it():
    (tx,) = parse_pages([BBVA_CARD_PAGE]).transactions
    result = structure("bbva", tx.description_raw, tx.merchant)
    assert tx.merchant == "SUPER ACME 0042 L"
    assert result.bank_concept == "PAGO CON TARJETA EN SUPERMERCADOS"
    assert result.merchant == "SUPER ACME 0042 L"
    assert result.card_last4 == "5678"


def test_bbva_line_without_detail_keeps_its_concept():
    result = structure("bbva", "CUOTA MENSUAL", None)
    assert result.bank_concept == "CUOTA MENSUAL"
    assert result.merchant is None
    assert result.card_last4 is None


def test_card_number_is_removed_from_the_concept():
    result = structure("bbva", "PAGO CON TARJETA 1111222233334444 ACME", None)
    assert result.bank_concept == "PAGO CON TARJETA ACME"
    assert result.card_last4 == "4444"


def test_text_without_a_card_number_is_left_as_is():
    """Like the backfill, which only rewrites rows that hold a card number."""
    result = structure("bbva", "PAGO  CON TARJETA", "ACME  SHOP")
    assert (result.bank_concept, result.merchant) == ("PAGO  CON TARJETA", "ACME  SHOP")


@pytest.mark.parametrize(("row", "expected"), BACKFILL_CASES)
def test_same_result_as_the_migration_backfill(row, expected):
    result = structure(*row)
    assert (result.bank_concept, result.merchant, result.card_last4) == expected
