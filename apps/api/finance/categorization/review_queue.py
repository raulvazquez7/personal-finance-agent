"""Group what needs review into one item per merchant (spec 11.1); rows without one stand alone.
A pending merge suggestion is a card of its own (quality of life spec 9)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from finance.categorization.taxonomy import Taxonomy
from finance.ingestion.structure import mask_card_numbers


class ReviewRow(BaseModel):
    id: UUID
    booked_at: date
    amount: Decimal
    description_raw: str
    account_name: str
    merchant_id: UUID | None
    merchant_name: str | None
    merchant_category_slug: str | None
    category_slug: str | None
    category_confidence: float | None
    category_probabilities: dict[str, float] | None
    is_subscription: bool


class ReviewTransaction(BaseModel):
    id: UUID
    booked_at: date
    amount: Decimal
    description_raw: str
    account_name: str


class CategoryScore(BaseModel):
    slug: str
    confidence: float


class Suggestion(BaseModel):
    category_slug: str | None
    level1: str | None
    confidence: float | None
    is_subscription: bool
    top: list[CategoryScore]


class MergeSuggestion(BaseModel):
    merchant_id: UUID
    name: str
    confidence: float


class MerchantOut(BaseModel):
    id: UUID
    name: str


class PendingMerge(BaseModel):
    merchant: MerchantOut  # the source, which the merge would fold into the suggestion
    suggestion: MergeSuggestion


class ReviewItem(BaseModel):
    key: str
    kind: Literal["merchant", "transaction", "merge"]
    merchant: MerchantOut | None
    transactions: list[ReviewTransaction]
    count: int
    total: Decimal
    suggestion: Suggestion
    merge: MergeSuggestion | None


def suggestion_for(rows: list[ReviewRow], taxonomy: Taxonomy) -> Suggestion:
    """The category with the highest average probability across the rows; level 1 follows it."""
    scored = [row for row in rows if row.category_probabilities]
    totals: dict[str, float] = defaultdict(float)
    for row in scored:
        for slug, probability in row.category_probabilities.items():
            totals[slug] += probability
    top = [
        CategoryScore(slug=slug, confidence=total / len(scored))
        for slug, total in sorted(totals.items(), key=lambda kv: -kv[1])[:3]
    ]
    slug = top[0].slug if top else rows[0].category_slug
    confidence = top[0].confidence if top else rows[0].category_confidence
    return Suggestion(
        category_slug=slug,
        level1=taxonomy.get(slug).level1 if slug else None,
        confidence=confidence,
        is_subscription=any(row.is_subscription for row in rows),
        top=top,
    )


def _joins_its_merchant(row: ReviewRow, taxonomy: Taxonomy) -> bool:
    """Every row of a merchant, purchases and refunds alike, is reviewed as one item: a refund
    takes the purchase's category (spec 2.2). Money going out is never income (spec 7.3), so it
    stands alone when the default is income: confirming it would overwrite that default."""
    if row.merchant_id is None:
        return False
    default = row.merchant_category_slug
    return not (row.amount < 0 and default and taxonomy.get(default).tx_type == "income")


def _transaction(row: ReviewRow) -> ReviewTransaction:
    """Card numbers in description_raw keep only their last four digits. The review and
    transactions APIs mask them; the full number stays in the database (spec 4.2)."""
    masked = mask_card_numbers(row.description_raw)
    return ReviewTransaction.model_validate(row.model_dump() | {"description_raw": masked})


def _merge_item(pending: PendingMerge) -> ReviewItem:
    return ReviewItem(
        key=f"merge:{pending.merchant.id}",
        kind="merge",
        merchant=pending.merchant,
        transactions=[],
        count=0,
        total=Decimal(0),
        suggestion=Suggestion(
            category_slug=None, level1=None, confidence=None, is_subscription=False, top=[]
        ),
        merge=pending.suggestion,
    )


def build_review_items(
    rows: list[ReviewRow], merges: list[PendingMerge], taxonomy: Taxonomy
) -> list[ReviewItem]:
    """Category cards first, largest total first; then merge cards, most confident first."""
    groups: dict[str, list[ReviewRow]] = defaultdict(list)
    for row in rows:
        key = f"m:{row.merchant_id}" if _joins_its_merchant(row, taxonomy) else f"t:{row.id}"
        groups[key].append(row)
    items = []
    for key, members in groups.items():
        first = members[0]
        merchant = (
            MerchantOut(id=first.merchant_id, name=first.merchant_name)
            if first.merchant_id
            else None
        )
        items.append(
            ReviewItem(
                key=key,
                kind="merchant" if key.startswith("m:") else "transaction",
                merchant=merchant,
                transactions=[_transaction(m) for m in members],
                count=len(members),
                total=sum((m.amount for m in members), Decimal(0)),
                suggestion=suggestion_for(members, taxonomy),
                merge=None,
            )
        )
    items.sort(key=lambda item: (-abs(item.total), item.key))
    ordered = sorted(merges, key=lambda m: (-m.suggestion.confidence, str(m.merchant.id)))
    return items + [_merge_item(pending) for pending in ordered]
