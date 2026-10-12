"""Render the data context the agent receives every turn, next to its instructions: the data
model with app-defined values, the metric definitions, the query examples, and today's date."""

from datetime import date
from textwrap import indent

from finance.agent.catalog import Account, Catalog, Category
from finance.agent.semantic_layer import Attribute, SemanticLayer

UNCATEGORIZED = "uncategorized"


def _sql_literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _category(c: Category) -> str:
    line = f"- {c.slug} (group {c.level1}, {c.tx_type}): {c.what}"
    return f"{line}. Not for: {c.not_for}" if c.not_for else line


def _groups(categories: list[Category]) -> list[str]:
    groups: dict[tuple[str, str], list[str]] = {}
    for c in categories:
        groups.setdefault((c.level1, c.tx_type), []).append(c.slug)
    return [
        f"- {level1} ({tx_type}): {', '.join(slugs)}" for (level1, tx_type), slugs in groups.items()
    ]


def _account(a: Account) -> str:
    if a.data_from is None:
        return f"- {_sql_literal(a.name)} ({a.bank}): no statements imported"
    return f"- {_sql_literal(a.name)} ({a.bank}): statements from {a.data_from} to {a.data_to}"


def _values(attribute: Attribute, catalog: Catalog) -> list[str]:
    source = attribute.allowed_values
    if source is None:
        return []
    if source == "categories":
        lines = [_category(c) for c in catalog.categories]
        return [*lines, f"- {UNCATEGORIZED}: no category yet; the movement counts by its sign"]
    if source == "category_groups":
        return [*_groups(catalog.categories), f"- {UNCATEGORIZED}: movements with no category yet"]
    if source == "accounts":
        return [_account(a) for a in catalog.accounts]
    return [f"- {v.value}: {v.meaning.strip()}" for v in source]


def render_data_context(
    layer: SemanticLayer, columns: dict[str, dict[str, str]], catalog: Catalog, today: date
) -> str:
    lines = ["# Data context", "", "## Data model"]
    for model in layer.models:
        lines += ["", f"### {model.model}", f"Description: {model.description.strip()}"]
        lines += [f"Grain: {model.grain.strip()}", "Use for:"]
        lines += [f"- {item.strip()}" for item in model.use_for]
        lines += ["Not for:"] + [f"- {item.strip()}" for item in model.not_for]
        lines.append("Columns:")
        for a in model.attributes:
            data_type = columns[model.model][a.attribute]
            lines.append(f"- {a.attribute} ({data_type}, {a.kind}): {a.description.strip()}")
            if values := _values(a, catalog):
                lines += ["  Allowed values:"] + [f"  {v}" for v in values]
    lines += ["", "## Metrics"]
    lines += [f"- {m.name} = {m.sql} on {m.model}: {m.description.strip()}" for m in layer.metrics]
    lines += ["", "## Query examples"]
    for number, example in enumerate(layer.examples, start=1):
        lines += ["", f"{number}. {example.question}", f"   Teaches: {example.teaches.strip()}"]
        for step, sql in enumerate(example.sql, start=1):
            label = "SQL" if len(example.sql) == 1 else f"Step {step}"
            lines += [f"   {label}:", indent(sql.strip(), "   ")]
    latest = catalog.latest_day.isoformat() if catalog.latest_day else "nothing imported yet"
    lines += ["", "## Now", f"Today: {today.isoformat()} ({today:%A})"]
    lines.append(f"Latest imported movement: {latest}")
    return "\n".join(lines) + "\n"
