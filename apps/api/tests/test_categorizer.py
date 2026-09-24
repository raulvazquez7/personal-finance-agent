import asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from finance.categorization.categorizer import CategorizationContext, categorize
from finance.categorization.merchants import MerchantRef, MerchantRoster
from finance.categorization.models import TxInput
from finance.categorization.rules import read_rules_yaml
from finance.categorization.seed import SEED_DIR
from finance.categorization.taxonomy import Taxonomy, read_categories_yaml
from finance.settings import Settings
from tests.fakes import FakeJev, jev_result

CTX = CategorizationContext(
    taxonomy=Taxonomy(read_categories_yaml(SEED_DIR / "categories.yaml")),
    rules=read_rules_yaml(SEED_DIR / "rules.yaml"),
    settings=Settings(),
)
GROCERIES = jev_result(
    merchant={"ACME": 0.97, "none": 0.03}, category={"groceries": 0.97, "restaurants_bars": 0.03}
)


def _tx(merchant, amount="-9.90", concept="PAGO CON TARJETA EN SUPERMERCADOS", day=1, **extra):
    return TxInput(
        id=uuid4(),
        bank="bbva",
        booked_at=date(2026, 7, day),
        amount=Decimal(amount),
        description_raw=f"{concept} | {merchant}",
        bank_concept=concept,
        merchant=merchant,
        **extra,
    )


def _run(rows, jev, roster=None, **kwargs):
    return asyncio.run(categorize(rows, CTX, jev, roster or MerchantRoster([]), **kwargs))


def test_paired_and_rule_rows_never_reach_jev():
    jev = FakeJev()
    paired = _tx("ANA EXAMPLE", concept="TRASPASO", transfer_pair_id=uuid4())
    bizum = _tx("ENVIADO: DINNER", concept="BIZUM")
    own, rule = _run([paired, bizum], jev)
    assert (own.category_slug, own.category_source, own.tx_type) == (
        "own_accounts",
        "rule",
        "transfer",
    )
    assert (rule.category_slug, rule.needs_review) == ("payments_to_people", False)
    assert jev.calls == []


def test_confident_jev_row_is_accepted_and_names_a_new_merchant():
    [result] = _run([_tx("ACME 0042")], FakeJev(first={"ACME 0042": GROCERIES}))
    assert (result.category_slug, result.category_source, result.needs_review) == (
        "groceries",
        "jev",
        False,
    )
    assert result.merchant_name == "ACME" and result.merchant_source == "jev"
    assert result.level1_confidence == 0.97 and result.model == "jev-test"


def test_second_row_of_the_same_merchant_uses_the_exact_key():
    jev = FakeJev(first={"ACME 0042": GROCERIES, "ACME C.C.": GROCERIES})
    _run([_tx("ACME 0042", day=1), _tx("ACME C.C.", day=2)], jev)
    assert [name for name, _ in jev.calls] == ["categorize", "categorize"]


def test_merchants_are_resolved_in_booking_order_not_row_order():
    foods = jev_result(merchant={"ACME FOODS": 0.97, "none": 0.03}, category={"groceries": 0.97})
    jev = FakeJev(
        first={"ACME FOODS 01": foods, "ACME 02": GROCERIES},
        same={"ACME FOODS": jev_result(known={"ACME": 0.9, "none": 0.1})},
    )
    roster = MerchantRoster([])
    later, earlier = _run([_tx("ACME FOODS 01", day=2), _tx("ACME 02", day=1)], jev, roster)
    assert [m.name for m in roster.new_merchants()] == ["ACME"]
    assert later.merchant_name == earlier.merchant_name == "ACME"


def test_the_card_number_in_the_raw_description_never_reaches_jev():
    tx = _tx("ACME").model_copy(update={"description_raw": "PAGO 4111111111111111 | ACME"})
    jev = FakeJev(first={"ACME": GROCERIES})
    _run([tx], jev)
    assert jev.calls and "4111111111111111" not in str(jev.calls)


def test_below_the_threshold_goes_to_review_with_probabilities():
    unsure = jev_result(
        merchant={"ACME": 0.9, "none": 0.1}, category={"groceries": 0.9, "restaurants_bars": 0.1}
    )
    [result] = _run([_tx("ACME")], FakeJev(first={"ACME": unsure}))
    assert result.needs_review and result.category_probabilities["restaurants_bars"] == 0.1


def test_dropped_brand_goes_to_review_without_a_merchant():
    weak = jev_result(
        merchant={"ACME": 0.4, "MADRID": 0.35, "none": 0.25},
        category={"groceries": 0.99, "fashion": 0.01},
    )
    [result] = _run([_tx("ACME MADRID")], FakeJev(first={"ACME MADRID": weak}))
    assert result.merchant_name is None and result.needs_review


def test_merchant_default_wins_over_jev_and_is_ignored_in_evals():
    roster = MerchantRoster(
        [
            MerchantRef(
                id=uuid4(), name="ACME", category_slug="restaurants_bars", is_subscription=False
            )
        ]
    )
    jev = FakeJev(first={"ACME": GROCERIES})
    [with_default] = _run([_tx("ACME")], jev, roster)
    [without] = _run([_tx("ACME")], jev, MerchantRoster(roster.all()), use_merchant_defaults=False)
    assert (with_default.category_slug, with_default.category_source) == (
        "restaurants_bars",
        "merchant",
    )
    assert with_default.category_probabilities["groceries"] == 0.97
    assert (without.category_slug, without.category_source) == ("groceries", "jev")


def test_expense_default_does_not_apply_to_a_refund():
    roster = MerchantRoster([MerchantRef(id=uuid4(), name="ACME", category_slug="fashion")])
    refund = jev_result(
        merchant={"ACME": 0.97, "none": 0.03}, category={"refunds": 0.97, "other_income": 0.03}
    )
    [result] = _run([_tx("ACME", amount="13.77")], FakeJev(first={"ACME": refund}), roster)
    assert (result.category_slug, result.category_source, result.tx_type) == (
        "refunds",
        "jev",
        "income",
    )


def test_subscription_flag_needs_an_expense_above_the_threshold():
    streaming = jev_result(
        merchant={"ACME TV": 0.99, "none": 0.01},
        category={"entertainment": 0.99, "software_ai": 0.01},
        subscription=0.9,
    )
    jev = FakeJev(first={"ACME TV": streaming})
    [charge] = _run([_tx("ACME TV", concept="PAGO CON TARJETA")], jev)
    [refund] = _run([_tx("ACME TV", amount="9.99", concept="PAGO CON TARJETA")], jev)
    assert charge.is_subscription and charge.subscription_score == 0.9
    assert not refund.is_subscription


def test_an_outgoing_transfer_is_never_a_subscription():
    plan = jev_result(
        merchant={"ACME INVEST": 0.99, "none": 0.01},
        category={"savings_investment": 0.99, "own_accounts": 0.01},
        subscription=0.9,
    )
    [result] = _run(
        [_tx("ACME INVEST", concept="TRANSFERENCIA")], FakeJev(first={"ACME INVEST": plan})
    )
    assert (result.tx_type, result.is_subscription) == ("transfer", False)


def test_merchant_default_skips_review_when_jev_is_unsure():
    roster = MerchantRoster(
        [MerchantRef(id=uuid4(), name="ACME", category_slug="restaurants_bars")]
    )
    unsure = jev_result(
        merchant={"ACME": 0.97, "none": 0.03}, category={"groceries": 0.6, "restaurants_bars": 0.4}
    )
    [result] = _run([_tx("ACME")], FakeJev(first={"ACME": unsure}), roster)
    assert (result.category_slug, result.category_source, result.needs_review) == (
        "restaurants_bars",
        "merchant",
        False,
    )


@pytest.mark.parametrize(
    ("default", "noul", "amount", "slug", "expected"),
    [
        (True, 0.05, "-9.99", "entertainment", True),
        (False, 0.9, "-9.99", "entertainment", False),
        (True, 0.9, "9.99", "refunds", False),
    ],
)
def test_merchant_subscription_default_overrides_jev_on_expenses_only(
    default, noul, amount, slug, expected
):
    roster = MerchantRoster([MerchantRef(id=uuid4(), name="ACME TV", is_subscription=default)])
    answer = jev_result(
        merchant={"ACME TV": 0.99, "none": 0.01}, category={slug: 1.0}, subscription=noul
    )
    [result] = _run([_tx("ACME TV", amount=amount)], FakeJev(first={"ACME TV": answer}), roster)
    assert result.is_subscription is expected


def test_the_category_edge_is_accepted_and_the_subscription_edge_is_not():
    settings = CTX.settings
    edge = jev_result(
        merchant={"ACME TV": 0.99, "none": 0.01},
        category={"entertainment": settings.category_threshold, "software_ai": 0.01},
        subscription=settings.subscription_threshold,
    )
    [result] = _run([_tx("ACME TV")], FakeJev(first={"ACME TV": edge}))
    assert result.category_confidence == settings.category_threshold
    assert not result.needs_review and not result.is_subscription
