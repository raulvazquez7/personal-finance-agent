"""The synthetic ledger behind the README screenshots. Deleted with the generator."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

import pytest

from finance.demo_ledger import (
    ACCOUNTS,
    EXPENSES,
    INCOME,
    MONTHS,
    build_ledger,
    require_scratch_docs,
)

INCOME_CATEGORIES = {"salary", "investment_income"}
TRANSFER = "own_accounts"


def _by_month(rows, keep):
    totals = defaultdict(Decimal)
    for row in rows:
        if keep(row):
            totals[(row.booked_at.year, row.booked_at.month)] += row.amount
    return totals


def test_every_month_lands_on_its_income_and_expense_totals():
    rows = build_ledger()
    income = _by_month(rows, lambda r: r.category in INCOME_CATEGORIES)
    expenses = _by_month(rows, lambda r: r.category not in INCOME_CATEGORIES | {TRANSFER})
    assert {m: str(v) for m, v in income.items()} == INCOME
    assert {m: str(-v) for m, v in expenses.items()} == EXPENSES


def test_twelve_full_months_ending_in_september_2026():
    rows = build_ledger()
    assert MONTHS[0] == (2025, 10) and MONTHS[-1] == (2026, 9) and len(MONTHS) == 12
    assert {(r.booked_at.year, r.booked_at.month) for r in rows} == set(MONTHS)
    assert max(r.booked_at for r in rows) <= date(2026, 9, 30)


def test_salary_is_the_same_in_ten_months():
    salaries = [r.amount for r in build_ledger() if r.category == "salary"]
    assert len(salaries) == 12
    assert salaries.count(Decimal("7540.31")) == 10


def test_groceries_stay_realistic_and_every_ticket_is_positive():
    rows = build_ledger()
    groceries = _by_month(rows, lambda r: r.category == "groceries")
    assert all(Decimal("550") <= -v <= Decimal("1100") for v in groceries.values())
    assert all(r.amount < 0 for r in rows if r.category == "groceries")


def test_amounts_are_cents_and_spending_is_money_out():
    rows = build_ledger()
    assert all(r.amount == r.amount.quantize(Decimal("0.01")) for r in rows)
    assert all(r.amount != 0 for r in rows)
    spending = [r for r in rows if r.category not in INCOME_CATEGORIES | {TRANSFER}]
    assert all(r.amount < 0 for r in spending)


def test_each_month_moves_savings_as_one_pair_that_nets_to_zero():
    rows = build_ledger()
    for month in MONTHS:
        pair = [
            r
            for r in rows
            if r.category == TRANSFER and (r.booked_at.year, r.booked_at.month) == month
        ]
        assert len(pair) == 2 and sum(r.amount for r in pair) == 0
        assert {r.account for r in pair} == set(ACCOUNTS)


def test_every_merchant_has_one_category_and_subscriptions_are_monthly_charges():
    rows = build_ledger()
    categories = defaultdict(set)
    for row in rows:
        if row.merchant:
            categories[row.merchant].add(row.category)
    assert all(len(slugs) == 1 for slugs in categories.values())
    subscriptions = {r.merchant for r in rows if r.subscription}
    assert len(subscriptions) == 4
    for merchant in subscriptions:
        assert sum(1 for r in rows if r.merchant == merchant) == 12


def test_only_fake_ibans_and_the_build_is_deterministic():
    assert all(iban.startswith("ES00") and len(iban) == 24 for _, iban in ACCOUNTS.values())
    assert build_ledger() == build_ledger()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
        "postgresql://postgres:postgres@127.0.0.1:54322/scratch_review",
        "postgresql://postgres:postgres@127.0.0.1:54322",
        "host=127.0.0.1 port=54322 dbname=postgres user=postgres",
    ],
)
def test_the_loader_refuses_any_database_but_scratch_docs(url):
    with pytest.raises(SystemExit):
        require_scratch_docs(url)


def test_the_loader_accepts_scratch_docs():
    require_scratch_docs("postgresql://postgres:postgres@127.0.0.1:54322/scratch_docs")
