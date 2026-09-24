import asyncio

import pytest

from finance.categorization.merchants import MerchantRef, MerchantRoster, resolve_merchant
from finance.settings import Settings
from tests.fakes import FakeJev, jev_result

STATE = {"merchant_text": "ACME FOODS MADRID"}


def _resolve(merchant_probs, roster, jev=None):
    answer = jev_result(merchant=merchant_probs).answers["merchant_name"]
    return asyncio.run(resolve_merchant(answer, STATE, roster, jev or FakeJev(), Settings()))


def _ask_same_merchant(known):
    """jev picks ACME and the roster holds ACME BAKERY, so the same-merchant question is asked."""
    roster = MerchantRoster([MerchantRef(name="ACME BAKERY")])
    jev = FakeJev(same={"ACME": jev_result(known=known)})
    result = _resolve({"ACME": 0.9, "none": 0.1}, roster, jev)
    assert [name for name, _ in jev.calls] == ["same_merchant"]
    return result, [m.name for m in roster.new_merchants()]


def test_none_means_no_merchant():
    result = _resolve({"none": 0.9, "ACME": 0.1}, MerchantRoster([]))
    assert result.merchant is None and not result.dropped


def test_nested_fragments_add_up_and_create_a_new_merchant():
    roster = MerchantRoster([])
    result = _resolve({"ACME": 0.4, "ACME FOODS": 0.35, "MADRID": 0.25}, roster)
    assert result.merchant.name == "ACME" and result.merchant.id is None
    assert abs(result.confidence - 0.75) < 1e-9
    assert [m.name for m in roster.new_merchants()] == ["ACME"]


def test_brand_below_the_threshold_is_dropped():
    result = _resolve({"ACME": 0.45, "MADRID": 0.3, "none": 0.25}, MerchantRoster([]))
    assert result.merchant is None and result.dropped


def test_brand_exactly_at_the_threshold_creates_the_merchant():
    result = _resolve({"ACME": 0.5, "MADRID": 0.3, "none": 0.2}, MerchantRoster([]))
    assert result.merchant.name == "ACME" and not result.dropped


def test_exact_key_reuses_a_known_merchant_without_asking_jev():
    known = MerchantRef(name="MC DONALD'S")
    jev = FakeJev()
    result = _resolve({"MCDONALDS": 0.9, "none": 0.1}, MerchantRoster([known]), jev)
    assert result.merchant is known and jev.calls == []


def test_a_known_merchant_is_reused_even_with_a_weak_brand():
    known = MerchantRef(name="ACME")
    jev = FakeJev()
    result = _resolve({"ACME": 0.45, "MADRID": 0.3, "none": 0.25}, MerchantRoster([known]), jev)
    assert result.merchant is known and not result.dropped and jev.calls == []
    assert abs(result.confidence - 0.45) < 1e-9


def test_same_merchant_answer_merges_suggests_or_creates():
    def run(confidence):
        return _ask_same_merchant({"ACME BAKERY": confidence, "none": 1 - confidence})

    merged, new = run(0.85)
    assert merged.merchant.name == "ACME BAKERY" and new == []
    suggested, new = run(0.6)
    assert suggested.merchant.name == "ACME" and suggested.merge_candidate.name == "ACME BAKERY"
    assert abs(suggested.merge_confidence - 0.6) < 1e-9 and new == ["ACME"]
    separate, new = run(0.3)
    assert separate.merchant.name == "ACME" and separate.merge_candidate is None
    assert new == ["ACME"]


@pytest.mark.parametrize(
    ("confidence", "merchant", "candidate", "new"),
    [
        (0.8, "ACME BAKERY", None, []),
        (0.5, "ACME", "ACME BAKERY", ["ACME"]),
        (0.49, "ACME", None, ["ACME"]),
    ],
)
def test_merge_and_suggestion_thresholds_are_inclusive(confidence, merchant, candidate, new):
    result, created = _ask_same_merchant({"ACME BAKERY": confidence, "none": 0.1})
    assert result.merchant.name == merchant
    assert getattr(result.merge_candidate, "name", None) == candidate and created == new


def test_filler_and_short_words_do_not_shortlist():
    roster = MerchantRoster([MerchantRef(name="BAKERY DEL OK SAU")])
    assert roster.shortlist("GRILL DEL OK SAU") == []
    assert [m.name for m in roster.shortlist("BAKERY")] == ["BAKERY DEL OK SAU"]


def test_add_returns_the_merchant_already_under_that_key():
    known = MerchantRef(name="MC DONALD'S")
    roster = MerchantRoster([known])
    assert roster.add("MCDONALDS") is known
    acme = roster.add("ACME")
    assert roster.add("Acme.") is acme
    assert roster.new_merchants() == [acme] and roster.get("MC DONALDS") is known
