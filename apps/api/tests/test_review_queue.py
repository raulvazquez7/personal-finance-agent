from datetime import date
from decimal import Decimal
from uuid import uuid4

from finance.categorization.review_queue import (
    MerchantOut,
    MergeSuggestion,
    PendingMerge,
    ReviewRow,
    build_review_items,
)
from finance.categorization.seed import SEED_DIR
from finance.categorization.taxonomy import Taxonomy, read_categories_yaml

TAXONOMY = Taxonomy(read_categories_yaml(SEED_DIR / "categories.yaml"))
ACME = uuid4()


def _row(
    amount,
    merchant_id=None,
    probabilities=None,
    subscription=False,
    default=None,
    description="PAGO | ACME",
):
    return ReviewRow(
        id=uuid4(),
        booked_at=date(2026, 7, 1),
        amount=Decimal(amount),
        description_raw=description,
        account_name="bbva ····0001",
        merchant_id=merchant_id,
        merchant_name="ACME" if merchant_id else None,
        merchant_category_slug=default,
        category_slug=max(probabilities, key=probabilities.get) if probabilities else None,
        category_confidence=max(probabilities.values()) if probabilities else None,
        category_probabilities=probabilities,
        is_subscription=subscription,
    )


def test_rows_of_a_merchant_become_one_item_with_a_summed_suggestion():
    rows = [
        _row("-10", ACME, {"groceries": 0.6, "restaurants_bars": 0.4}),
        _row("-20", ACME, {"groceries": 0.8, "restaurants_bars": 0.2}),
        _row("-500", None, {"payments_to_people": 0.7, "uncategorized_expense": 0.3}),
    ]
    items = build_review_items(rows, [], TAXONOMY)
    assert [item.kind for item in items] == ["transaction", "merchant"]  # largest total first
    merchant = items[1]
    assert (merchant.count, merchant.total) == (2, Decimal("-30"))
    assert merchant.suggestion.category_slug == "groceries"
    assert merchant.suggestion.level1 == "shopping"
    assert abs(merchant.suggestion.confidence - 0.7) < 1e-9
    assert [s.slug for s in merchant.suggestion.top] == ["groceries", "restaurants_bars"]


def _pending_merge(confidence=0.6):
    return PendingMerge(
        merchant=MerchantOut(id=ACME, name="ACME"),
        suggestion=MergeSuggestion(merchant_id=uuid4(), name="ACME FOODS", confidence=confidence),
    )


def test_a_merge_without_review_rows_is_its_own_card():
    pending = _pending_merge()
    [item] = build_review_items([], [pending], TAXONOMY)
    assert (item.key, item.kind, item.transactions, item.count) == (f"merge:{ACME}", "merge", [], 0)
    assert (item.merchant, item.merge) == (pending.merchant, pending.suggestion)


def test_a_merge_and_a_review_row_of_one_merchant_are_two_cards():
    pending = _pending_merge()
    row = _row("-10", ACME, {"groceries": 1.0})
    merchant, merge = build_review_items([row], [pending], TAXONOMY)
    assert (merchant.kind, [tx.id for tx in merchant.transactions], merchant.merge) == (
        "merchant",
        [row.id],
        None,
    )
    assert (merge.kind, merge.merge) == ("merge", pending.suggestion)


def test_merge_cards_follow_the_category_cards_by_confidence():
    low = _pending_merge(0.4)
    high = PendingMerge(
        merchant=MerchantOut(id=uuid4(), name="OTHER"),
        suggestion=MergeSuggestion(merchant_id=uuid4(), name="OTHER CO", confidence=0.9),
    )
    items = build_review_items([_row("-1", None, {"groceries": 1.0})], [low, high], TAXONOMY)
    assert [item.kind for item in items] == ["transaction", "merge", "merge"]
    assert [item.merge.confidence for item in items[1:]] == [0.9, 0.4]


def test_subscription_is_suggested_when_any_row_is_flagged():
    rows = [
        _row("-9.99", ACME, {"entertainment": 0.9, "software_ai": 0.1}, subscription=True),
        _row("-9.99", ACME, {"entertainment": 0.9, "software_ai": 0.1}),
    ]
    assert build_review_items(rows, [], TAXONOMY)[0].suggestion.is_subscription


def test_a_refund_joins_its_merchant_item():
    pending = _pending_merge()
    rows = [
        _row("-20", ACME, {"groceries": 0.8, "restaurants_bars": 0.2}, default="groceries"),
        _row("15", ACME, {"groceries": 0.7, "restaurants_bars": 0.3}, default="groceries"),
    ]
    item, merge = build_review_items(rows, [pending], TAXONOMY)
    assert (item.key, item.kind, item.count, item.total) == (
        f"m:{ACME}",
        "merchant",
        2,
        Decimal("-5"),
    )
    assert item.merge is None
    assert (merge.key, merge.merge) == (f"merge:{ACME}", pending.suggestion)


def test_money_out_of_a_merchant_with_an_income_default_stands_alone():
    default = "payments_from_people"
    money_out = _row(
        "-30", ACME, {"payments_to_people": 0.6, "restaurants_bars": 0.4}, default=default
    )
    money_in = _row("50", ACME, {"payments_from_people": 0.9, "salary": 0.1}, default=default)
    items = {item.key: item for item in build_review_items([money_out, money_in], [], TAXONOMY)}
    assert set(items) == {f"t:{money_out.id}", f"m:{ACME}"}
    assert items[f"t:{money_out.id}"].kind == "transaction"
    assert [tx.id for tx in items[f"m:{ACME}"].transactions] == [money_in.id]


def test_rows_in_the_direction_of_the_default_stay_grouped():
    rows = [
        _row("-10", ACME, {"groceries": 0.6, "restaurants_bars": 0.4}, default="groceries"),
        _row("-20", ACME, {"groceries": 0.8, "restaurants_bars": 0.2}, default="groceries"),
    ]
    [item] = build_review_items(rows, [], TAXONOMY)
    assert (item.key, item.kind, item.count) == (f"m:{ACME}", "merchant", 2)


def test_a_merchant_without_a_default_groups_both_directions():
    rows = [
        _row("-10", ACME, {"groceries": 0.6, "restaurants_bars": 0.4}),
        _row("15", ACME, {"refunds": 0.6, "other_income": 0.4}),
    ]
    [item] = build_review_items(rows, [], TAXONOMY)
    assert (item.kind, item.count, item.total) == ("merchant", 2, Decimal("5"))


def test_card_numbers_are_masked_and_long_references_kept():
    card = _row("-9.90", description="PAGO CON TARJETA | 1234567812345678 SUPER ACME")
    transfer = _row("-50", description="TRANSFERENCIA REF 12345678901234567890")
    items = build_review_items([card, transfer], [], TAXONOMY)
    descriptions = {item.transactions[0].id: item.transactions[0].description_raw for item in items}
    assert descriptions[card.id] == "PAGO CON TARJETA | •••• 5678 SUPER ACME"
    assert descriptions[transfer.id] == "TRANSFERENCIA REF 12345678901234567890"
