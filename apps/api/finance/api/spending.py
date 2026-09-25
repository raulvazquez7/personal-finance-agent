"""One scope's page: a group, a category, a merchant, or income (spec 6, 7.1)."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter

from finance.api.deps import Db
from finance.api.periods import PeriodQuery, resolve_request
from finance.dashboard.breakdowns import breakdown
from finance.dashboard.filters import Scope
from finance.dashboard.models import Cumulative, SpendingDetail
from finance.dashboard.totals import cumulative, scope_months, totals
from finance.dashboard.transactions import TransactionFilters, page

router = APIRouter(prefix="/spending", tags=["spending"])


@router.get("/detail")
def detail(
    conn: Db,
    query: PeriodQuery,
    type: Literal["expense", "income"] = "expense",
    level1: str | None = None,
    category: str | None = None,
    merchant_id: UUID | None = None,
) -> SpendingDetail:
    resolved = resolve_request(conn, query)
    before = resolved.comparable
    scope = Scope(
        accounts=query.accounts,
        tx_type=type,
        level1=level1,
        category=category,
        merchant_id=merchant_id,
    )
    value = "spend" if type == "expense" else "income"
    child = None if merchant_id else ("merchant" if category else "category")
    now = totals(conn, scope, resolved.current)
    amount = now.expenses if type == "expense" else now.income
    previous_total = None
    if before:
        then = totals(conn, scope, before)
        previous_total = then.expenses if type == "expense" else then.income
    children = (
        breakdown(
            conn,
            child,
            value,
            scope,
            resolved.current,
            before,
            top=None if child == "category" else 10,
        )
        if child
        else []
    )
    keys = [c.key for c in children if c.key != "_other"][:5]
    months = scope_months(conn, scope, value, resolved.current.end, child, keys)
    if any("_other" in m.by_child for m in months):  # every stacked-bar bucket is a series
        keys.append("_other")
    listing = page(conn, TransactionFilters(scope=scope), resolved, limit=5)
    name = None
    if merchant_id:
        row = conn.execute("select name from merchants where id = %s", (merchant_id,)).fetchone()
        name = row["name"] if row else None
    return SpendingDetail(
        period=resolved.out,
        type=type,
        level1=level1,
        category=category,
        merchant_id=merchant_id,
        merchant_name=name,
        total=amount,
        previous_total=previous_total,
        count=listing.count,
        months=months,
        child_keys=keys,
        children=children,
        top_merchants=breakdown(conn, "merchant", value, scope, resolved.current, before)
        if child == "category"
        else [],
        cumulative=Cumulative(
            current=cumulative(conn, scope, resolved.current, value, until=resolved.out.latest_day),
            previous=cumulative(conn, scope, before, value) if before else None,
        ),
        latest=listing.items,
    )
