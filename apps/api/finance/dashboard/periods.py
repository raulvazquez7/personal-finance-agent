"""Periods and their comparison: the previous period of the same length (spec 2.6)."""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

PeriodName = Literal["month", "last_3_months", "ytd", "last_12_months", "custom"]


class Period(BaseModel):
    start: date
    end: date  # inclusive


def month_end(day: date) -> date:
    return day.replace(day=monthrange(day.year, day.month)[1])


def add_months(day: date, months: int) -> date:
    """The first day of the month `months` away from `day`'s month."""
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def resolve(
    name: PeriodName,
    anchor: date,
    month: date | None = None,
    start: date | None = None,
    end: date | None = None,
) -> Period:
    """`anchor` is the latest day with data (statements arrive in batches); `month` is the
    first day of a chosen calendar month."""
    if name == "custom":
        if start is None or end is None or start > end:
            raise ValueError("a custom period needs start and end, with start <= end")
        return Period(start=start, end=end)
    last = month or anchor.replace(day=1)
    if name == "month":
        return Period(start=last, end=month_end(last))
    if name == "ytd":
        return Period(start=date(last.year, 1, 1), end=month_end(last))
    count = 3 if name == "last_3_months" else 12
    return Period(start=add_months(last, 1 - count), end=month_end(last))


def _year_back(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:  # 29 February
        return day.replace(year=day.year - 1, day=28)


def previous(name: PeriodName, period: Period) -> Period:
    """August -> July, a quarter -> the quarter before, year to date -> the same dates a year
    earlier, a custom range -> the same number of days just before it."""
    if name == "ytd":
        return Period(start=_year_back(period.start), end=_year_back(period.end))
    if period.start.day == 1 and period.end == month_end(period.end):
        count = len(months_between(period.start, period.end))
        return Period(
            start=add_months(period.start, -count), end=month_end(add_months(period.start, -1))
        )
    days = (period.end - period.start).days + 1
    return Period(start=period.start - timedelta(days=days), end=period.start - timedelta(days=1))


def months_between(start: date, end: date) -> list[str]:
    out, cursor = [], start.replace(day=1)
    while cursor <= end:
        out.append(f"{cursor:%Y-%m}")
        cursor = add_months(cursor, 1)
    return out


def savings_rate(income: Decimal, savings: Decimal) -> float | None:
    """Savings ÷ income; empty without income; negative when spending beats income."""
    return None if income <= 0 else round(float(savings / income), 4)
