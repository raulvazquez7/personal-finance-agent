"""The overview and the subscriptions page (spec 6, 7.1)."""

from dataclasses import replace

from fastapi import APIRouter

from finance.api.deps import Db
from finance.api.periods import PeriodQuery, resolve_request
from finance.dashboard.breakdowns import breakdown, group_slots
from finance.dashboard.filters import Scope
from finance.dashboard.models import Cumulative, Overview, Subscriptions
from finance.dashboard.subscriptions import active_subscriptions, summary
from finance.dashboard.totals import cumulative, month_series, totals

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
def overview(conn: Db, query: PeriodQuery) -> Overview:
    resolved = resolve_request(conn, query)
    scope = Scope(accounts=query.accounts)
    spend = replace(scope, tx_type="expense")
    before = resolved.comparable
    return Overview(
        period=resolved.out,
        kpis=totals(conn, scope, resolved.current),
        previous_kpis=totals(conn, scope, before) if before else None,
        cumulative=Cumulative(
            current=cumulative(
                conn, spend, resolved.current, "spend", until=resolved.out.latest_day
            ),
            previous=cumulative(conn, spend, before, "spend") if before else None,
        ),
        months=month_series(conn, scope, resolved.current.end),
        by_group=breakdown(conn, "group", "spend", spend, resolved.current, before),
        by_category=breakdown(conn, "category", "spend", spend, resolved.current, before),
        by_merchant=breakdown(conn, "merchant", "spend", spend, resolved.current, before),
        group_slots=group_slots(conn),
        subscriptions=summary(active_subscriptions(conn)),
    )


@router.get("/subscriptions")
def subscriptions(conn: Db) -> Subscriptions:
    return active_subscriptions(conn)
