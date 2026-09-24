import pytest

from finance.categorization.rules import match_rule, read_rules_yaml
from finance.categorization.seed import SEED_DIR

RULES = read_rules_yaml(SEED_DIR / "rules.yaml")

# (bank, bank_concept, merchant, direction, expected category or None). Synthetic text.
FIXTURES = [
    (
        "bbva",
        "RET. EFECTIVO A DEBITO CON TARJ. EN CAJERO. AUT.",
        "01820000 999",
        "outgoing",
        "atm_withdrawal",
    ),
    ("caixabank", None, "REINT.CAJERO", "outgoing", "atm_withdrawal"),
    ("bbva", "ADEUDO MENSUAL DE TARJETA", None, "outgoing", "credit_card_payment"),
    ("caixabank", None, "T. VISA CLASSIC", "outgoing", "credit_card_payment"),
    ("bbva", "BIZUM", "ENVIADO: DINNER", "outgoing", "payments_to_people"),
    ("bbva", "BIZUM", "RECIBIDO: BIZUM DE ANA", "incoming", "payments_from_people"),
    ("caixabank", None, "BIZUM ENVIADO", "outgoing", "payments_to_people"),
    ("caixabank", None, "BIZUM RECIBIDO", "incoming", "payments_from_people"),
    ("caixabank", None, "ENVIADO: COMPRA SUPER", "outgoing", "payments_to_people"),
    ("caixabank", None, "TRASPASO PROPIO", "outgoing", "own_accounts"),
    ("caixabank", None, "TRASPASO PROPIO", "incoming", "own_accounts"),
    ("bbva", "PAGO CON TARJETA EN SUPERMERCADOS", "SUPER ACME 0042", "outgoing", None),
    ("bbva", "TRASPASO", "ANA EXAMPLE", "outgoing", None),
    ("bbva", "PAGO CON TARJETA EN RESTAURANTES Y CAFETERIAS", "BIZUMBAR", "outgoing", None),
    ("caixabank", None, "NOMINA (TRF)", "incoming", None),
]


@pytest.mark.parametrize(("bank", "concept", "merchant", "direction", "expected"), FIXTURES)
def test_seed_rules_on_fixtures(bank, concept, merchant, direction, expected):
    rule = match_rule(RULES, bank, concept, merchant, direction)
    assert (rule.category_slug if rule else None) == expected


@pytest.mark.parametrize(("bank", "concept", "merchant", "direction", "expected"), FIXTURES)
def test_no_fixture_matches_rules_with_different_categories(
    bank, concept, merchant, direction, expected
):
    categories = {
        rule.category_slug
        for rule in RULES
        if match_rule([rule], bank, concept, merchant, direction) is not None
    }
    assert len(categories) <= 1


def test_rule_limited_to_a_bank_ignores_other_banks():
    rule = RULES[0].model_copy(update={"bank": "caixabank"})
    assert match_rule([rule], "bbva", "RET. EFECTIVO X", None, "outgoing") is None


def test_rule_without_a_bank_applies_to_every_bank():
    rule = RULES[0].model_copy(update={"bank": None})
    for bank in ("bbva", "caixabank"):
        assert match_rule([rule], bank, "RET. EFECTIVO X", None, "outgoing") is rule


def test_rule_for_any_direction_matches_both_directions():
    rule = RULES[0].model_copy(update={"direction": "any"})
    for direction in ("outgoing", "incoming"):
        assert match_rule([rule], "bbva", "RET. EFECTIVO X", None, direction) is rule
