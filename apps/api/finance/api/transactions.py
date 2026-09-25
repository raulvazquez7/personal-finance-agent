"""Routes for listing transactions, labelling one of them and editing its note."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from finance.api.categories import require_category
from finance.api.deps import Db
from finance.api.periods import PeriodQuery, resolve_request
from finance.categorization.labels import NotFound, label_transaction, set_note
from finance.categorization.models import CategorySource
from finance.dashboard.filters import Scope
from finance.dashboard.models import Transaction, TransactionPage  # noqa: F401  (schema name)
from finance.dashboard.transactions import Saved, TransactionFilters, page

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
def list_transactions(
    conn: Db,
    query: PeriodQuery,
    q: str | None = Query(default=None, max_length=100),
    tx_type: Literal["expense", "income", "transfer"] | None = None,
    level1: str | None = None,
    category: str | None = None,
    merchant_id: UUID | None = None,
    is_subscription: bool | None = None,
    category_source: CategorySource | None = None,
    needs_review: bool | None = None,
    saved: Saved | None = None,
    cursor: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}_[0-9a-f-]{36}$"),
    limit: int = Query(default=100, ge=1, le=100),
) -> TransactionPage:
    resolved = resolve_request(conn, query)
    scope = Scope(
        accounts=query.accounts,
        tx_type=tx_type,
        level1=level1,
        category=category,
        merchant_id=merchant_id,
    )
    filters = TransactionFilters(scope, q, is_subscription, category_source, needs_review, saved)
    return page(conn, filters, resolved, cursor, limit)


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
