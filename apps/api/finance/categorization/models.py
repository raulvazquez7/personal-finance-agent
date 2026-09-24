"""Input and output of the categorizer; the database is not involved."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from finance.categorization.taxonomy import TxType
from finance.models import Bank

CategorySource = Literal["rule", "merchant", "jev", "user", "none"]


class TxInput(BaseModel):
    id: UUID
    bank: Bank
    booked_at: date
    amount: Decimal
    description_raw: str
    bank_concept: str | None = None
    merchant: str | None = None
    transfer_pair_id: UUID | None = None


class Categorization(BaseModel):
    transaction_id: UUID
    tx_type: TxType
    category_slug: str
    category_source: CategorySource
    category_confidence: float | None = None
    level1_confidence: float | None = None
    category_probabilities: dict[str, float] | None = None
    merchant_name: str | None = None
    merchant_source: Literal["jev", "user", "none"] = "none"
    merchant_confidence: float | None = None
    merge_candidate_name: str | None = None
    merge_confidence: float | None = None
    is_subscription: bool = False
    subscription_score: float | None = None
    transfer_pair_id: UUID | None = None
    needs_review: bool = False
    model: str | None = None
