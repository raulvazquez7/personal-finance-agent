import pytest

from finance.agent.semantic_layer import (
    SemanticLayerError,
    check_layer,
    layer_version,
    load_semantic_layer,
)
from finance.agent.sql_guard import check_query


def _columns(layer):
    return {m.model: {a.attribute: "text" for a in m.attributes} for m in layer.models}


def test_the_yaml_loads_into_two_models_with_metrics_and_examples():
    layer = load_semantic_layer()
    assert [m.model for m in layer.models] == ["subscriptions", "transactions"]
    assert [m.name for m in layer.metrics] == [
        "expenses",
        "income",
        "savings",
        "savings_rate",
        "net_cash_flow",
    ]
    assert len(layer.examples) == 12


def test_the_layer_matches_columns_named_like_its_attributes():
    layer = load_semantic_layer()
    check_layer(layer, _columns(layer))  # does not raise


def test_every_mismatch_with_the_views_is_listed():
    layer = load_semantic_layer()
    columns = _columns(layer)
    del columns["transactions"]["note"]
    columns["transactions"]["shiny_new_column"] = "text"
    del columns["subscriptions"]
    with pytest.raises(SemanticLayerError) as raised:
        check_layer(layer, columns)
    message = str(raised.value)
    assert "transactions.note: not a column" in message
    assert "transactions.shiny_new_column: not described" in message
    assert "subscriptions: no such view in schema agent" in message


def test_only_dimensions_carry_allowed_values():
    layer = load_semantic_layer()
    spend = next(a for a in layer.models[1].attributes if a.attribute == "spend")
    spend.allowed_values = "categories"
    with pytest.raises(SemanticLayerError, match="transactions.spend: only a dimension"):
        check_layer(layer, _columns(layer))


def test_a_typo_in_the_yaml_fails_to_load(tmp_path):
    (tmp_path / "metrics.yaml").write_text("[]")
    (tmp_path / "examples.yaml").write_text("[]")
    (tmp_path / "t.yaml").write_text(
        "model: t\ndescription: d\ngrain: g\nuse_for: []\nnot_for: []\n"
        "attributes:\n  - attribute: a\n    kind: dimension\n    descripton: typo\n"
    )
    with pytest.raises(ValueError, match="descripton"):
        load_semantic_layer(tmp_path)


def test_every_example_step_passes_the_sql_guard():
    for example in load_semantic_layer().examples:
        for sql in example.sql:
            check_query(sql)  # raises RejectedQuery on a bad example


def test_the_version_is_a_stable_short_hash():
    assert layer_version() == layer_version() and len(layer_version()) == 12
