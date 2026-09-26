"""The period query parameters every dashboard read takes (spec 2.6, 6)."""

from dataclasses import dataclass
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query
from psycopg import Connection

from finance.dashboard.filters import has_data, latest_day
from finance.dashboard.models import PeriodOut
from finance.dashboard.periods import Period, PeriodName, previous, resolve, until_same_day


@dataclass(frozen=True)
class PeriodRequest:
    name: PeriodName
    month: date | None
    start: date | None
    end: date | None
    accounts: tuple[UUID, ...]


# Bounded years: ASCII digits only, and no period whose previous one falls before year 1.
_FIRST_DAY, _LAST_DAY = date(1900, 1, 1), date(2100, 12, 31)


def period_request(
    period: PeriodName = "month",
    month: str | None = Query(default=None, pattern=r"^(19|20)[0-9]{2}-(0[1-9]|1[0-2])$"),
    start: date | None = Query(default=None, ge=_FIRST_DAY, le=_LAST_DAY),
    end: date | None = Query(default=None, ge=_FIRST_DAY, le=_LAST_DAY),
    account_id: list[UUID] = Query(default=[]),
) -> PeriodRequest:
    first = date.fromisoformat(f"{month}-01") if month else None
    return PeriodRequest(period, first, start, end, tuple(account_id))


PeriodQuery = Annotated[PeriodRequest, Depends(period_request)]


@dataclass(frozen=True)
class Resolved:
    current: Period
    previous: Period  # the whole previous period: the cumulative chart's reference line
    cut: Period  # the previous period after as many days as the data covers (until_same_day)
    out: PeriodOut

    @property
    def comparable(self) -> Period | None:
        """The cut previous period, which every change compares with, when the previous period
        has data; otherwise no delta is shown."""
        return self.cut if self.out.has_previous else None


def resolve_request(conn: Connection, request: PeriodRequest) -> Resolved:
    latest = latest_day(conn, request.accounts)
    try:
        current = resolve(
            request.name, latest or date.today(), request.month, request.start, request.end
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    whole = previous(request.name, current)
    # One cut for the whole page: the tiles and the change columns compare it, and the same-day
    # card agrees with them when the data ends inside the period (a whole period is not cut).
    cut = until_same_day(whole, current, latest)
    out = PeriodOut(
        name=request.name,
        start=current.start,
        end=current.end,
        previous_start=cut.start,
        previous_end=cut.end,
        # Judged on the whole period (spec 2.6): rows only after the cut day still count.
        has_previous=has_data(conn, whole, request.accounts),
        latest_day=latest,
    )
    return Resolved(current, whole, cut, out)
