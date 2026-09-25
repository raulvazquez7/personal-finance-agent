"""Routes for listing transactions, labelling one of them and editing its note."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from finance.api.categories import require_category
from finance.api.deps import Db
from finance.categorization.labels import NotFound, label_transaction, set_note
from finance.ingestion.structure import mask_card_numbers

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
    return [
        Transaction.model_validate(
            row | {"description_raw": mask_card_numbers(row["description_raw"])}
        )
        for row in conn.execute(_SELECT, params).fetchall()
    ]


class LabelTransaction(BaseModel):
    category_slug: str
    is_subscription: bool = False
    merchant_id: UUID | None = None
    new_merchant_name: str | None = Field(default=None, min_length=1)


@router.post("/{transaction_id}/label", status_code=204)
def label(transaction_id: UUID, body: LabelTransaction, conn: Db) -> Response:
    require_category(conn, body.category_slug)
    try:
        label_transaction(
            conn,
            transaction_id,
            body.category_slug,
            body.is_subscription,
            body.merchant_id,
            body.new_merchant_name,
        )
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:  # a merchant name with no letter or digit, or income on money out
        raise HTTPException(status_code=422, detail=str(error)) from error
    return Response(status_code=204)


class NoteUpdate(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.patch("/{transaction_id}", status_code=204)
def update_note(transaction_id: UUID, body: NoteUpdate, conn: Db) -> Response:
    try:
        set_note(conn, transaction_id, body.note)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)
