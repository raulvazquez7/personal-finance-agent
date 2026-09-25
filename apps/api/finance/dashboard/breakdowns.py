"""Where the money went: by group, category or merchant, top N plus "_other" (spec 7.1)."""

from decimal import Decimal
from typing import Literal

from psycopg import Connection

from finance.dashboard.filters import WHERE, Scope
from finance.dashboard.models import BreakdownRow
from finance.dashboard.periods import Period

Dimension = Literal["group", "category", "merchant"]
Value = Literal["spend", "income"]

KEYS: dict[str, str] = {
    "group": "coalesce(level1, 'uncategorized')",
    "category": "coalesce(category_slug, 'uncategorized')",
    "merchant": (
        "coalesce(merchant_id::text, 'category:' || coalesce(category_slug, 'uncategorized'))"
    ),
}


def _query(dimension: Dimension, value: Value) -> str:
    # Both names come from the fixed dictionaries above, never from a request.
    return f"""
select {KEYS[dimension]} as key, max(merchant_name) as label, max(level1) as level1,
       max(category_slug) as category_slug, max(merchant_id::text) as merchant_id,
       sum({value}) as amount, count(*) as n
from v_transactions_enriched where {WHERE}
group by 1
"""


def _share(amount: Decimal, total: Decimal) -> float:
    return 0.0 if total <= 0 else round(float(amount / total), 4)


def breakdown(
    conn: Connection,
    dimension: Dimension,
    value: Value,
    scope: Scope,
    period: Period,
    previous: Period | None,
    top: int | None = 5,
) -> list[BreakdownRow]:
    """Sorted by amount, largest first; a negative entry (refunds only) sorts last. `previous`
    is None when the previous period has no data, so no delta is shown."""
    rows = conn.execute(_query(dimension, value), scope.params(period)).fetchall()
    before = (
        {
            r["key"]: r["amount"]
            for r in conn.execute(_query(dimension, value), scope.params(previous)).fetchall()
        }
        if previous
        else {}
    )
    total = sum((r["amount"] for r in rows), Decimal(0))
    out = [
        BreakdownRow(
            key=r["key"],
            label=r["label"] if dimension == "merchant" else None,
            level1=r["level1"] or ("uncategorized" if dimension == "group" else None),
            category_slug=r["category_slug"] if dimension != "group" else None,
            merchant_id=r["merchant_id"] if dimension == "merchant" else None,
            amount=r["amount"],
            share=_share(r["amount"], total),
            previous=before.get(r["key"], Decimal(0)) if previous else None,
            count=r["n"],
        )
        for r in rows
    ]
    out.sort(key=lambda row: (-row.amount, row.key))
    if top is None or len(out) <= top + 1:
        return out
    head, tail = out[:top], out[top:]
    amount = sum((row.amount for row in tail), Decimal(0))
    other_previous = (
        sum(before.values(), Decimal(0))
        - sum((before.get(h.key, Decimal(0)) for h in head), Decimal(0))
        if previous
        else None
    )
    head.append(
        BreakdownRow(
            key="_other",
            label=None,
            level1=None,
            category_slug=None,
            merchant_id=None,
            amount=amount,
            share=_share(amount, total),
            previous=other_previous,
            count=sum(row.count for row in tail),
            folded=len(tail),
        )
    )
    return head


def group_slots(conn: Connection) -> dict[str, int]:
    """Colour slots 1..5 for the groups with the most all-time spend: a period filter never
    repaints them (spec 7.2)."""
    rows = conn.execute(
        "select level1 from v_transactions_enriched"
        " where tx_type = 'expense' and level1 is not null"
        " group by level1 order by sum(spend) desc, level1 limit 5"
    ).fetchall()
    return {row["level1"]: slot for slot, row in enumerate(rows, start=1)}
