from decimal import Decimal

from finance.categorization.jev_questions import (
    first_call_questions,
    fragments,
    jev_state,
    match_key,
    same_merchant_question,
    significant_words,
)
from finance.categorization.seed import SEED_DIR
from finance.categorization.taxonomy import Taxonomy, read_categories_yaml

TAXONOMY = Taxonomy(read_categories_yaml(SEED_DIR / "categories.yaml"))


def test_fragments_drop_codes_and_keep_word_runs():
    assert fragments("SUPER ACME 0042 L") == [
        "SUPER",
        "ACME",
        "SUPER ACME",
        "ACME L",
        "SUPER ACME L",
    ]


def test_fragments_split_web_prefixes_and_never_carry_digits():
    assert fragments("WWW.AMAZON* F641Z7X25") == ["WWW", "AMAZON", "WWW AMAZON"]
    assert fragments("1234567812345678 ACME") == ["ACME"]
    assert fragments("") == []


def test_match_key_ignores_spaces_and_punctuation():
    assert match_key("Mc Donald's") == match_key("MCDONALDS") == "MCDONALDS"


def test_significant_words_skip_legal_suffixes_and_short_words():
    assert significant_words("ACME FOODS SL DE") == {"ACME", "FOODS"}


def test_state_never_contains_a_card_number_field():
    state = jev_state("bbva", "PAGO CON TARJETA EN SUPERMERCADOS", "SUPER ACME", Decimal("-9.90"))
    assert state == {
        "bank": "bbva",
        "bank_concept": "PAGO CON TARJETA EN SUPERMERCADOS",
        "merchant_text": "SUPER ACME",
        "amount": "-9.90",
        "direction": "outgoing",
    }


def test_first_call_asks_three_independent_questions():
    leaves = TAXONOMY.leaves("outgoing")
    questions = first_call_questions(leaves, ["ACME", "SUPER ACME"])
    assert set(questions) == {"merchant_name", "category", "is_subscription"}
    assert set(questions["merchant_name"]["criteria"]) == {"ACME", "SUPER ACME", "none"}
    assert set(questions["category"]["criteria"]) == {c.slug for c in leaves}
    assert questions["category"]["criteria"]["groceries"]["group"] == "shopping"
    assert "not_for" not in questions["category"]["criteria"]["groceries"]
    assert "not_for" in questions["category"]["criteria"]["mortgage"]
    assert questions["is_subscription"]["type"] == "noul"
    assert "electricity" in questions["is_subscription"]["instructions"]["not_for"]


def test_same_merchant_question_offers_names_and_none():
    question = same_merchant_question(["ACME FOODS", "ACME BAR"])["known_merchant"]
    assert set(question["criteria"]) == {"ACME FOODS", "ACME BAR", "none"}
