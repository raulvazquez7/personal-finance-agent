"""The period query parameters every dashboard read takes (spec 2.6, 6)."""

from dataclasses import dataclass
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query
from psycopg import Connection

from finance.dashboard.filters import has_data, latest_day
from finance.dashboard.models import PeriodOut
from finance.dashboard.periods import Period, PeriodName, previous, resolve


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
    previous: Period
    out: PeriodOut

    @property
    def comparable(self) -> Period | None:
        """The previous period when it has data; otherwise no delta is shown."""
        return self.previous if self.out.has_previous else None


def resolve_request(conn: Connection, request: PeriodRequest) -> Resolved:
    latest = latest_day(conn, request.accounts)
    try:
        current = resolve(
            request.name, latest or date.today(), request.month, request.start, request.end
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    before = previous(request.name, current)
    out = PeriodOut(
        name=request.name,
        start=current.start,
        end=current.end,
        previous_start=before.start,
        previous_end=before.end,
        has_previous=has_data(conn, before, request.accounts),
        latest_day=latest,
    )
    return Resolved(current, before, out)
