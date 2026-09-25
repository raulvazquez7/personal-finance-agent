"""The explorer: filters, search, cursor paging and totals over the whole filtered set."""

from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import UUID

from psycopg import Connection

from finance.dashboard.filters import WHERE, Scope
from finance.dashboard.models import Transaction, TransactionPage
from finance.ingestion.structure import mask_card_numbers

Saved = Literal["unpaired_own", "refunds"]

_FILTERS = (
    WHERE
    + r"""
and (%(q)s::text is null or merchant_name ilike %(pattern)s or bank_merchant_text ilike %(pattern)s
     or description_raw ilike %(pattern)s or note ilike %(pattern)s)
and (%(is_subscription)s::boolean is null or is_subscription = %(is_subscription)s)
and (%(category_source)s::text is null or category_source = %(category_source)s)
and (%(needs_review)s::boolean is null or needs_review = %(needs_review)s)
and (%(saved)s::text is null
     or (%(saved)s = 'unpaired_own' and category_slug = 'own_accounts' and transfer_pair_id is null)
     or (%(saved)s = 'refunds' and tx_type = 'expense' and amount > 0))
"""
)

_PAGE = f"""
select id, booked_at, account_id, account_name, amount, description_raw, bank_merchant_text,
       merchant_id, merchant_name, tx_type, category_slug, level1, category_source,
       is_subscription, needs_review, note, transfer_pair_id
from v_transactions_enriched
where {_FILTERS}
  and (%(cursor_day)s::date is null or (booked_at, id) < (%(cursor_day)s, %(cursor_id)s::uuid))
order by booked_at desc, id desc
limit %(limit)s
"""

_TOTALS = f"""
select count(*) as n,
       coalesce(sum(amount) filter (where amount > 0), 0) as money_in,
       coalesce(-sum(amount) filter (where amount < 0), 0) as money_out
from v_transactions_enriched where {_FILTERS}
"""


@dataclass(frozen=True)
class TransactionFilters:
    scope: Scope
    q: str | None = None
    is_subscription: bool | None = None
    category_source: str | None = None
    needs_review: bool | None = None
    saved: Saved | None = None


def _like(text: str) -> str:
    """Search is literal: % and _ typed by the user are not wildcards."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _cursor(value: str | None) -> tuple[date | None, UUID | None]:
    if not value:
        return None, None
    day, _, row_id = value.partition("_")
    return date.fromisoformat(day), UUID(row_id)


def page(
    conn: Connection,
    filters: TransactionFilters,
    resolved,
    cursor: str | None = None,
    limit: int = 100,
) -> TransactionPage:
    q = (filters.q or "").strip() or None
    cursor_day, cursor_id = _cursor(cursor)
    params = filters.scope.params(resolved.current) | {
        "q": q,
        "pattern": _like(q) if q else None,
        "is_subscription": filters.is_subscription,
        "category_source": filters.category_source,
        "needs_review": filters.needs_review,
        "saved": filters.saved,
        "cursor_day": cursor_day,
        "cursor_id": cursor_id,
        "limit": limit + 1,  # one extra row tells whether another page exists
    }
    rows = conn.execute(_PAGE, params).fetchall()
    more = len(rows) > limit
    rows = rows[:limit]
    items = [
        Transaction.model_validate(
            row | {"description_raw": mask_card_numbers(row["description_raw"])}
        )
        for row in rows
    ]
    total = conn.execute(_TOTALS, params).fetchone()
    last = items[-1] if items else None
    return TransactionPage(
        period=resolved.out,
        items=items,
        next_cursor=f"{last.booked_at.isoformat()}_{last.id}" if more and last else None,
        count=total["n"],
        money_in=total["money_in"],
        money_out=total["money_out"],
    )
