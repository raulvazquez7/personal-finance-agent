from datetime import date

from finance.agent.catalog import Account, Catalog, Category
from finance.agent.data_context import render_data_context
from finance.agent.semantic_layer import (
    AllowedValue,
    Attribute,
    Example,
    Metric,
    Model,
    SemanticLayer,
    load_semantic_layer,
)

CATALOG = Catalog(
    categories=[
        Category("groceries", "shopping", "expense", "supermarkets, bakeries", None),
        Category("rent", "home", "expense", "monthly rent", "mortgage instalments"),
    ],
    accounts=[
        Account("BBVA ····0001", "bbva", date(2025, 1, 1), date(2025, 12, 31)),
        Account("Joe's savings", "caixabank", None, None),
    ],
    latest_day=date(2025, 12, 31),
)

TINY = SemanticLayer(
    models=[
        Model(
            model="transactions",
            description="Every movement.\n",
            grain="One row per movement.",
            use_for=["Spending."],
            not_for=["Balances."],
            attributes=[
                Attribute(attribute="spend", kind="measure", description="Money spent."),
                Attribute(
                    attribute="direction",
                    kind="dimension",
                    description="In or out.",
                    allowed_values=[AllowedValue(value="incoming", meaning="money in")],
                ),
                Attribute(
                    attribute="category",
                    kind="dimension",
                    description="Category.",
                    allowed_values="categories",
                ),
                Attribute(
                    attribute="category_group",
                    kind="dimension",
                    description="Group.",
                    allowed_values="category_groups",
                ),
                Attribute(
                    attribute="account",
                    kind="dimension",
                    description="Account.",
                    allowed_values="accounts",
                ),
            ],
        )
    ],
    metrics=[Metric(name="expenses", model="transactions", description="Total.", sql="SUM(spend)")],
    examples=[Example(question="July?", teaches="SUM(spend).", sql=["SELECT 1", "SELECT 2"])],
)
COLUMNS = {
    "transactions": {
        "spend": "numeric",
        "direction": "text",
        "category": "text",
        "category_group": "text",
        "account": "text",
    }
}

EXPECTED = """\
# Data context

## Data model

### transactions
Description: Every movement.
Grain: One row per movement.
Use for:
- Spending.
Not for:
- Balances.
Columns:
- spend (numeric, measure): Money spent.
- direction (text, dimension): In or out.
  Allowed values:
  - incoming: money in
- category (text, dimension): Category.
  Allowed values:
  - groceries (group shopping, expense): supermarkets, bakeries
  - rent (group home, expense): monthly rent. Not for: mortgage instalments
  - uncategorized: no category yet; the movement counts by its sign
- category_group (text, dimension): Group.
  Allowed values:
  - shopping (expense): groceries
  - home (expense): rent
  - uncategorized: movements with no category yet
- account (text, dimension): Account.
  Allowed values:
  - 'BBVA ····0001' (bbva): statements from 2025-01-01 to 2025-12-31
  - 'Joe''s savings' (caixabank): no statements imported

## Metrics
- expenses = SUM(spend) on transactions: Total.

## Query examples

1. July?
   Teaches: SUM(spend).
   Step 1:
   SELECT 1
   Step 2:
   SELECT 2

## Now
Today: 2026-01-05 (Monday)
Latest imported movement: 2025-12-31
"""


def test_the_rendered_context_is_exactly_this_text():
    assert render_data_context(TINY, COLUMNS, CATALOG, date(2026, 1, 5)) == EXPECTED


def test_the_real_layer_renders_every_attribute_with_its_type_within_budget():
    layer = load_semantic_layer()
    columns = {m.model: {a.attribute: "text" for a in m.attributes} for m in layer.models}
    text = render_data_context(layer, columns, CATALOG, date(2026, 1, 5))
    for model in layer.models:
        for a in model.attributes:
            assert f"- {a.attribute} (text, {a.kind}): " in text
    # about 8,000 tokens: the spec measures about 6,000 for a real taxonomy
    assert len(text) < 32_000


def test_an_empty_ledger_says_nothing_is_imported_yet():
    empty = Catalog(categories=CATALOG.categories, accounts=[], latest_day=None)
    text = render_data_context(TINY, COLUMNS, empty, date(2026, 1, 5))
    assert "Latest imported movement: nothing imported yet" in text
