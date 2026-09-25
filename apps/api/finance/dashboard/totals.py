"""KPIs, the 12-month series and cumulative daily sums over v_transactions_enriched."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from psycopg import Connection

from finance.dashboard.filters import WHERE, Scope, data_months
from finance.dashboard.models import CumulativePoint, MonthPoint, Totals
from finance.dashboard.periods import Period, add_months, month_end, months_between, savings_rate

Value = Literal["spend", "income"]

_TOTALS = f"""
select coalesce(sum(income), 0) as income, coalesce(sum(spend), 0) as expenses
from v_transactions_enriched where {WHERE}
"""

_MONTHS = f"""
select month, sum(income) as income, sum(spend) as expenses
from v_transactions_enriched where {WHERE}
group by month
"""

_DAILY = {
    value: f"select booked_at, sum({value}) as amount from v_transactions_enriched"
    f" where {WHERE} group by booked_at"
    for value in ("spend", "income")
}


def totals(conn: Connection, scope: Scope, period: Period) -> Totals:
    row = conn.execute(_TOTALS, scope.params(period)).fetchone()
    savings = row["income"] - row["expenses"]
    return Totals(
        income=row["income"],
        expenses=row["expenses"],
        savings=savings,
        savings_rate=savings_rate(row["income"], savings),
    )


def twelve_months(end: date, count: int = 12) -> Period:
    return Period(start=add_months(end.replace(day=1), 1 - count), end=month_end(end))


def month_series(conn: Connection, scope: Scope, end: date, count: int = 12) -> list[MonthPoint]:
    """A month without imported data is `has_data = false`, never zeros (spec 2.6)."""
    period = twelve_months(end, count)
    with_data = data_months(conn, period, scope.accounts)
    found = {r["month"]: r for r in conn.execute(_MONTHS, scope.params(period)).fetchall()}
    points = []
    for month in months_between(period.start, period.end):
        if month not in with_data:
            points.append(
                MonthPoint(month=month, has_data=False, income=None, expenses=None, savings=None)
            )
            continue
        row = found.get(month) or {"income": Decimal(0), "expenses": Decimal(0)}
        points.append(
            MonthPoint(
                month=month,
                has_data=True,
                income=row["income"],
                expenses=row["expenses"],
                savings=row["income"] - row["expenses"],
            )
        )
    return points


def cumulative(
    conn: Connection, scope: Scope, period: Period, value: Value, until: date | None = None
) -> list[CumulativePoint]:
    """Running total per day; the current period stops at the latest imported day."""
    daily = {
        r["booked_at"]: r["amount"]
        for r in conn.execute(_DAILY[value], scope.params(period)).fetchall()
    }
    last = min(period.end, until) if until else period.end
    points, total, day = [], Decimal(0), period.start
    while day <= last:
        total += daily.get(day, Decimal(0))
        points.append(CumulativePoint(day=(day - period.start).days + 1, date=day, total=total))
        day += timedelta(days=1)
    return points
