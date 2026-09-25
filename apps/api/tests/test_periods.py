from datetime import date
from decimal import Decimal

import pytest

from finance.dashboard.periods import Period, months_between, previous, resolve, savings_rate

AUG_20 = date(2026, 8, 20)


@pytest.mark.parametrize(
    ("name", "expected", "before"),
    [
        ("month", (date(2026, 8, 1), date(2026, 8, 31)), (date(2026, 7, 1), date(2026, 7, 31))),
        (
            "last_3_months",
            (date(2026, 6, 1), date(2026, 8, 31)),
            (date(2026, 3, 1), date(2026, 5, 31)),
        ),
        (
            "last_12_months",
            (date(2025, 9, 1), date(2026, 8, 31)),
            (date(2024, 9, 1), date(2025, 8, 31)),
        ),
        ("ytd", (date(2026, 1, 1), date(2026, 8, 31)), (date(2025, 1, 1), date(2025, 8, 31))),
    ],
)
def test_periods_and_their_previous_period(name, expected, before):
    period = resolve(name, AUG_20)
    assert (period.start, period.end) == expected
    earlier = previous(name, period)
    assert (earlier.start, earlier.end) == before


def test_a_chosen_month_and_january_roll_back_a_year():
    period = resolve("month", AUG_20, month=date(2026, 1, 1))
    assert previous("month", period) == Period(start=date(2025, 12, 1), end=date(2025, 12, 31))


def test_a_custom_range_compares_with_the_same_number_of_days_before():
    period = resolve("custom", AUG_20, start=date(2026, 8, 10), end=date(2026, 8, 19))
    assert previous("custom", period) == Period(start=date(2026, 7, 31), end=date(2026, 8, 9))
    with pytest.raises(ValueError):
        resolve("custom", AUG_20, start=date(2026, 8, 19), end=date(2026, 8, 10))


def test_year_to_date_on_a_leap_day():
    period = Period(start=date(2028, 1, 1), end=date(2028, 2, 29))
    assert previous("ytd", period).end == date(2027, 2, 28)


def test_months_between_and_the_savings_rate():
    assert months_between(date(2025, 11, 5), date(2026, 2, 1)) == [
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
    ]
    assert savings_rate(Decimal("2000"), Decimal("-300")) == -0.15
    assert savings_rate(Decimal("0"), Decimal("-30")) is None
