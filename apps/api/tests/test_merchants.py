import asyncio

from finance.categorization.merchants import MerchantRef, MerchantRoster, resolve_merchant
from finance.settings import Settings
from tests.fakes import FakeJev, jev_result

STATE = {"merchant_text": "ACME FOODS MADRID"}


def _resolve(merchant_probs, roster, jev=None):
    answer = jev_result(merchant=merchant_probs).answers["merchant_name"]
    return asyncio.run(resolve_merchant(answer, STATE, roster, jev or FakeJev(), Settings()))


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


def test_exact_key_reuses_a_known_merchant_without_asking_jev():
    known = MerchantRef(name="MC DONALD'S")
    jev = FakeJev()
    result = _resolve({"MCDONALDS": 0.9, "none": 0.1}, MerchantRoster([known]), jev)
    assert result.merchant is known and jev.calls == []


def test_same_merchant_answer_merges_suggests_or_creates():
    def run(confidence):
        roster = MerchantRoster([MerchantRef(name="ACME BAKERY")])
        same = {"ACME": jev_result(known={"ACME BAKERY": confidence, "none": 1 - confidence})}
        return _resolve({"ACME": 0.9, "none": 0.1}, roster, FakeJev(same=same))

    merged, suggested, separate = run(0.85), run(0.6), run(0.3)
    assert merged.merchant.name == "ACME BAKERY"
    assert suggested.merchant.name == "ACME" and suggested.merge_candidate.name == "ACME BAKERY"
    assert abs(suggested.merge_confidence - 0.6) < 1e-9
    assert separate.merchant.name == "ACME" and separate.merge_candidate is None
