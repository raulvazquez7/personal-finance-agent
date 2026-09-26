from datetime import date
from decimal import Decimal

import pytest

from finance.dashboard.periods import (
    Period,
    months_between,
    previous,
    resolve,
    savings_rate,
    until_same_day,
)

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


@pytest.mark.parametrize(
    ("name", "latest", "cut"),
    [
        ("month", date(2026, 8, 10), (date(2026, 7, 1), date(2026, 7, 10))),
        ("last_3_months", date(2026, 8, 10), (date(2026, 3, 1), date(2026, 5, 10))),
        ("ytd", date(2026, 8, 10), (date(2025, 1, 1), date(2025, 8, 10))),
        ("month", date(2026, 3, 30), (date(2026, 2, 1), date(2026, 2, 28))),  # February is shorter
    ],
)
def test_data_that_ends_inside_the_period_cuts_the_previous_one_at_as_many_days(name, latest, cut):
    period = resolve(name, latest)
    before = until_same_day(previous(name, period), period, latest)
    assert (before.start, before.end) == cut


def test_a_custom_range_whose_data_ends_early_is_cut_the_same_way():
    period = resolve("custom", AUG_20, start=date(2026, 8, 10), end=date(2026, 8, 19))
    cut = until_same_day(previous("custom", period), period, date(2026, 8, 15))
    assert cut == Period(start=date(2026, 7, 31), end=date(2026, 8, 5))  # six days each


@pytest.mark.parametrize(
    "latest",
    [date(2026, 8, 31), date(2026, 9, 3), date(2026, 7, 20), None],
    ids=["ends-with-the-period", "after-it", "before-it", "no-data"],
)
def test_the_previous_period_stays_whole_unless_the_data_ends_inside_the_period(latest):
    period = resolve("month", AUG_20)
    whole = previous("month", period)
    assert until_same_day(whole, period, latest) == whole


def test_months_between_and_the_savings_rate():
    assert months_between(date(2025, 11, 5), date(2026, 2, 1)) == [
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
    ]
    assert savings_rate(Decimal("2000"), Decimal("-300")) == -0.15
    assert savings_rate(Decimal("0"), Decimal("-30")) is None
