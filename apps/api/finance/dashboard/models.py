"""Response models of the dashboard, spending and transactions APIs (spec 6)."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from finance.categorization.models import CategorySource
from finance.categorization.taxonomy import TxType
from finance.dashboard.periods import PeriodName


class PeriodOut(BaseModel):
    name: PeriodName
    start: date
    end: date
    previous_start: date
    previous_end: date
    has_previous: bool
    latest_day: date | None


class Totals(BaseModel):
    income: Decimal
    expenses: Decimal
    savings: Decimal
    savings_rate: float | None


class CumulativePoint(BaseModel):
    day: int  # 1 = the period's first day
    date: date
    total: Decimal


class Cumulative(BaseModel):
    current: list[CumulativePoint]
    previous: list[CumulativePoint] | None


class MonthPoint(BaseModel):
    month: str  # YYYY-MM
    has_data: bool
    income: Decimal | None
    expenses: Decimal | None
    savings: Decimal | None


class BreakdownRow(BaseModel):
    # The folded rest is "_other", never "other": the expense level 1 `other` is a real slug.
    key: str  # a level1 or category slug, a merchant id, "category:<slug>" or "_other"
    label: str | None  # merchant name; the web labels slugs
    level1: str | None
    category_slug: str | None
    merchant_id: UUID | None
    amount: Decimal
    share: float
    previous: Decimal | None  # None when the previous period has no data; 0 = "new"
    count: int
    folded: int = 0  # entries folded into "_other"


class SubscriptionOut(BaseModel):
    merchant_id: UUID
    merchant_name: str
    cadence: Literal["monthly", "yearly"]
    typical_amount: Decimal
    monthly_equivalent: Decimal
    last_charge: date
    charges: int


class Subscriptions(BaseModel):
    items: list[SubscriptionOut]
    monthly_total: Decimal
    yearly_total: Decimal


class SubscriptionsSummary(BaseModel):
    count: int
    monthly_total: Decimal
    yearly_total: Decimal


class Overview(BaseModel):
    period: PeriodOut
    kpis: Totals
    previous_kpis: Totals | None
    cumulative: Cumulative
    months: list[MonthPoint]
    by_group: list[BreakdownRow]
    by_category: list[BreakdownRow]
    by_merchant: list[BreakdownRow]
    group_slots: dict[str, int]  # level1 -> colour slot 1..5 by all-time spend
    subscriptions: SubscriptionsSummary


class Transaction(BaseModel):
    id: UUID
    booked_at: date
    account_id: UUID
    account_name: str
    amount: Decimal
    description_raw: str
    bank_merchant_text: str | None
    merchant_id: UUID | None
    merchant_name: str | None
    tx_type: TxType
    category_slug: str | None
    level1: str | None
    category_source: CategorySource
    is_subscription: bool
    needs_review: bool
    note: str | None
    transfer_pair_id: UUID | None


class TransactionPage(BaseModel):
    period: PeriodOut
    items: list[Transaction]
    next_cursor: str | None
    count: int
    money_in: Decimal
    money_out: Decimal


class ScopeMonth(BaseModel):
    month: str
    has_data: bool
    total: Decimal | None
    by_child: dict[str, Decimal]  # child key (or "_other") -> amount; empty without children


class SpendingDetail(BaseModel):
    period: PeriodOut
    type: Literal["expense", "income"]
    level1: str | None
    category: str | None
    merchant_id: UUID | None
    merchant_name: str | None
    total: Decimal
    previous_total: Decimal | None
    count: int
    months: list[ScopeMonth]
    child_keys: list[str]  # the stacked-bar series, largest first ("_other" last)
    children: list[BreakdownRow]
    top_merchants: list[BreakdownRow]
    cumulative: Cumulative
    latest: list[Transaction]
