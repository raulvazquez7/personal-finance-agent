from datetime import date
from decimal import Decimal

from finance.ingestion.dedup import dedup_key, occurrence_indexes
from finance.models import NormalizedTransaction


def tx(
    amount: str, description: str = "COFFEE", balance: str | None = "10.00"
) -> NormalizedTransaction:
    return NormalizedTransaction(
        booked_at=date(2026, 7, 1),
        amount=Decimal(amount),
        description_raw=description,
        balance_after=None if balance is None else Decimal(balance),
    )


def test_occurrence_indexes_count_identical_rows_within_a_file():
    rows = [tx("-1.00"), tx("-1.00"), tx("-2.00"), tx("-1.00")]
    assert occurrence_indexes(rows) == [0, 1, 0, 2]


def test_dedup_key_is_stable_and_ignores_spacing_and_case():
    a = dedup_key("ES0000", tx("-1.00", "Mercadona  3087"), 0)
    b = dedup_key("ES0000", tx("-1.00", "MERCADONA 3087"), 0)
    assert a == b
    assert len(a) == 64


def test_dedup_key_changes_with_occurrence_index_and_account():
    base = dedup_key("ES0000", tx("-1.00"), 0)
    assert dedup_key("ES0000", tx("-1.00"), 1) != base
    assert dedup_key("ES1111", tx("-1.00"), 0) != base


def test_dedup_key_handles_missing_balance():
    assert dedup_key("ES0000", tx("-1.00", balance=None), 0) != dedup_key("ES0000", tx("-1.00"), 0)
