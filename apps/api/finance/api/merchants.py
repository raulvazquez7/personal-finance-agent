"""Merchant autocomplete, the merchant profile and the merchant-level review actions."""

from typing import Literal, Self
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, model_validator

from finance.api.categories import require_category
from finance.api.deps import Db
from finance.categorization.labels import (
    NotFound,
    clear_merchant_default,
    confirm_merchant,
    dismiss_merge,
    rename_merchant,
)
from finance.categorization.review_queue import MerchantOut

router = APIRouter(prefix="/merchants", tags=["merchants"])


Cadence = Literal["monthly", "quarterly", "yearly"]


class CadenceUpdate(BaseModel):
    cadence: Cadence | None


class MerchantProfile(BaseModel):
    id: UUID
    name: str
    category_slug: str | None
    is_subscription: bool | None
    cadence: Cadence | None
    # From v_subscriptions: null when the merchant has no flagged charges.
    cadence_effective: Cadence | None
    cadence_source: Literal["auto", "user"] | None
    rows_a_default_would_change: int


class MerchantRename(BaseModel):
    name: str | None = None
    merge_into_id: UUID | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.name is None) == (self.merge_into_id is None):
            raise ValueError("send either name or merge_into_id")
        return self


class MerchantRef(BaseModel):
    id: UUID


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


# The rows _RELABEL_MERCHANT can touch: ones a user or a rule labelled stay as they are.
_PROFILE = """
select m.id, m.name, m.category_slug, m.is_subscription, m.cadence,
       s.cadence as cadence_effective, s.cadence_source,
       (select count(*) from transactions t where t.merchant_id = m.id
          and t.category_source in ('jev', 'merchant', 'none')) as rows_a_default_would_change
from merchants m
left join v_subscriptions s on s.merchant_id = m.id
where m.id = %s
"""


@router.get("/{merchant_id}")
def merchant_profile(merchant_id: UUID, conn: Db) -> MerchantProfile:
    row = conn.execute(_PROFILE, (merchant_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"merchant {merchant_id}")
    return MerchantProfile.model_validate(row)


@router.patch("/{merchant_id}")
def rename(merchant_id: UUID, body: MerchantRename, conn: Db) -> MerchantRef:
    try:
        survivor = rename_merchant(conn, merchant_id, body.name, body.merge_into_id)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:  # a name with no letter or digit
        raise HTTPException(status_code=422, detail=str(error)) from error
    return MerchantRef(id=survivor)


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


@router.patch("/{merchant_id}/cadence", status_code=204)
def set_cadence(merchant_id: UUID, body: CadenceUpdate, conn: Db) -> Response:
    row = conn.execute(
        "update merchants set cadence = %s where id = %s returning id",
        (body.cadence, merchant_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"merchant {merchant_id}")
    return Response(status_code=204)
