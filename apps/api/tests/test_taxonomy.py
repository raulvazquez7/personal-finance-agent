from decimal import Decimal

import pytest

from finance.categorization.rules import read_rules_yaml
from finance.categorization.seed import SEED_DIR, seed
from finance.categorization.taxonomy import (
    Taxonomy,
    direction_of,
    load_taxonomy,
    read_categories_yaml,
)
from finance.db import connection

CATEGORIES = read_categories_yaml(SEED_DIR / "categories.yaml")
TAXONOMY = Taxonomy(CATEGORIES)


def test_seed_has_the_spec_taxonomy():
    assert len(CATEGORIES) == 57
    assert len({c.slug for c in CATEGORIES}) == 57
    assert len({c.level1 for c in CATEGORIES if c.tx_type == "expense"}) == 15
    assert all(c.what for c in CATEGORIES)


def test_leaves_follow_the_direction():
    outgoing = {c.slug for c in TAXONOMY.leaves("outgoing")}
    incoming = {c.slug for c in TAXONOMY.leaves("incoming")}
    assert "groceries" in outgoing and "groceries" not in incoming
    assert "salary" in incoming and "salary" not in outgoing
    assert "own_accounts" in outgoing and "own_accounts" in incoming


def test_level1_sums_add_leaf_probabilities():
    sums = TAXONOMY.level1_sums({"groceries": 0.5, "fashion": 0.3, "restaurants_bars": 0.2})
    assert sums == {"shopping": 0.8, "leisure": 0.2}


def test_tx_type_comes_from_the_category_or_the_sign():
    assert TAXONOMY.tx_type_of("own_accounts", Decimal("-5")) == "transfer"
    assert TAXONOMY.tx_type_of("groceries", Decimal("-5")) == "expense"
    assert TAXONOMY.tx_type_of("refunds", Decimal("5")) == "income"
    assert direction_of(Decimal("-0.01")) == "outgoing"


def test_every_rule_points_to_a_known_category():
    slugs = {c.slug for c in CATEGORIES}
    rules = read_rules_yaml(SEED_DIR / "rules.yaml")
    assert {rule.category_slug for rule in rules if rule.category_slug} <= slugs


@pytest.mark.integration
def test_load_taxonomy_keeps_the_yaml_order():
    """jev sees its options in the spike-validated order, whatever order the rows sit on disk."""
    with connection() as conn, conn.transaction(force_rollback=True):
        seed(conn)
        for category in reversed(CATEGORIES):  # rewritten rows leave the heap out of YAML order
            conn.execute("update categories set what = what where slug = %s", (category.slug,))
        assert load_taxonomy(conn).categories() == CATEGORIES


def test_the_row_type_follows_the_category_not_the_sign():
    assert TAXONOMY.tx_type_of("fashion", Decimal("80")) == "expense"  # a refund
    assert TAXONOMY.tx_type_of("fashion", Decimal("-80")) == "expense"
    assert TAXONOMY.tx_type_of("salary", Decimal("2000")) == "income"
    assert TAXONOMY.tx_type_of("own_accounts", Decimal("50")) == "transfer"
