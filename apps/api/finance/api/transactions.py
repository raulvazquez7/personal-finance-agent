"""Route for listing transactions, optionally filtered by account and month."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from finance.api.deps import Db

router = APIRouter(prefix="/transactions", tags=["transactions"])

_SELECT = """
select t.id, a.name as account_name, t.booked_at, t.amount, t.description_raw, t.merchant,
       t.tx_type, t.category_slug
from transactions t
join accounts a on a.id = t.account_id
where (%(account_id)s::uuid is null or t.account_id = %(account_id)s)
  and (%(month)s::text is null or to_char(t.booked_at, 'YYYY-MM') = %(month)s)
order by t.booked_at desc, t.created_at desc
limit %(limit)s
"""


class Transaction(BaseModel):
    id: UUID
    account_name: str
    booked_at: date
    amount: Decimal
    description_raw: str
    merchant: str | None
    tx_type: str
    category_slug: str | None


@router.get("")
def list_transactions(
    conn: Db,
    account_id: UUID | None = None,
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[Transaction]:
    params = {"account_id": account_id, "month": month, "limit": limit}
    return [Transaction.model_validate(row) for row in conn.execute(_SELECT, params).fetchall()]
