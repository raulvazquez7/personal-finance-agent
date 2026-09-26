"""Merchant autocomplete and the merchant-level review actions."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from finance.api.categories import require_category
from finance.api.deps import Db
from finance.categorization.labels import (
    NotFound,
    clear_merchant_default,
    confirm_merchant,
    dismiss_merge,
)
from finance.categorization.review_queue import MerchantOut

router = APIRouter(prefix="/merchants", tags=["merchants"])


class ConfirmMerchant(BaseModel):
    category_slug: str
    # Required, like the note: null keeps the merchant's flag and its rows' marks (money in has
    # no subscription switch), so leaving it out must not mean either answer.
    is_subscription: bool | None
    name: str | None = None
    merge_into_id: UUID | None = None


@router.get("")
def list_merchants(
    conn: Db, q: str | None = None, limit: int = Query(default=20, ge=1, le=5000)
) -> list[MerchantOut]:
    rows = conn.execute(
        "select id, name from merchants where %(q)s::text is null or name ilike %(pattern)s"
        " order by name limit %(limit)s",
        {"q": q, "pattern": f"%{q}%", "limit": limit},
    ).fetchall()
    return [MerchantOut.model_validate(row) for row in rows]


@router.post("/{merchant_id}/review", status_code=204)
def review_merchant(merchant_id: UUID, body: ConfirmMerchant, conn: Db) -> Response:
    require_category(conn, body.category_slug)
    try:
        confirm_merchant(
            conn,
            merchant_id,
            body.category_slug,
            body.is_subscription,
            body.name,
            body.merge_into_id,
        )
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:  # a new name with no letter or digit
        raise HTTPException(status_code=422, detail=str(error)) from error
    return Response(status_code=204)


@router.delete("/{merchant_id}/default", status_code=204)
def clear_default(merchant_id: UUID, conn: Db) -> Response:
    try:
        clear_merchant_default(conn, merchant_id)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)


@router.post("/{merchant_id}/dismiss-merge", status_code=204)
def dismiss(merchant_id: UUID, conn: Db) -> Response:
    try:
        dismiss_merge(conn, merchant_id)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)
