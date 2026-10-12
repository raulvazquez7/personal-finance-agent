"""The semantic layer: what the agent knows about its views (slice 4 spec, section 5).

Model knowledge and attributes, metric definitions and query examples live in YAML next to this
module, reviewed in pull requests. Column types and app-defined values come from the database.
"""

from hashlib import sha256
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

SEMANTIC_DIR = Path(__file__).parent / "semantic"
_NOT_MODELS = {"metrics", "examples"}

Kind = Literal["measure", "dimension", "time", "text", "flag"]
# Values read from the database when the data context is built (data_context.py).
ValueSource = Literal["accounts", "categories", "category_groups"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a typo in the YAML fails, not silently drops


class AllowedValue(_Strict):
    value: str
    meaning: str


class Attribute(_Strict):
    attribute: str
    kind: Kind
    description: str
    allowed_values: list[AllowedValue] | ValueSource | None = None


class Model(_Strict):
    model: str
    description: str
    grain: str
    use_for: list[str]
    not_for: list[str]
    attributes: list[Attribute]


class Metric(_Strict):
    name: str
    model: str
    description: str
    sql: str


class Example(_Strict):
    question: str
    teaches: str
    sql: list[str]  # one statement per step; lookups come before the final query


class SemanticLayer(_Strict):
    models: list[Model]
    metrics: list[Metric]
    examples: list[Example]


class SemanticLayerError(Exception):
    pass


def load_semantic_layer(directory: Path = SEMANTIC_DIR) -> SemanticLayer:
    def read(path: Path) -> object:
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    models = [read(p) for p in sorted(directory.glob("*.yaml")) if p.stem not in _NOT_MODELS]
    return SemanticLayer(
        models=models,
        metrics=read(directory / "metrics.yaml"),
        examples=read(directory / "examples.yaml"),
    )


def layer_version(directory: Path = SEMANTIC_DIR) -> str:
    """A short hash of the YAML files, recorded on every trace."""
    digest = sha256()
    for path in sorted(directory.glob("*.yaml")):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def check_layer(layer: SemanticLayer, columns: dict[str, dict[str, str]]) -> None:
    """Raise SemanticLayerError listing every mismatch with the live views (view -> column ->
    type). Every column must be described and every description must name a column."""
    problems = []
    for model in layer.models:
        live = columns.get(model.model)
        if live is None:
            problems.append(f"{model.model}: no such view in schema agent")
            continue
        described = [a.attribute for a in model.attributes]
        problems += [f"{model.model}.{c}: not a column" for c in described if c not in live]
        problems += [f"{model.model}.{c}: not described" for c in live if c not in described]
        problems += [
            f"{model.model}.{a.attribute}: only a dimension has allowed values"
            for a in model.attributes
            if a.allowed_values is not None and a.kind != "dimension"
        ]
    names = {model.model for model in layer.models}
    problems += [
        f"metric {m.name}: unknown model {m.model}" for m in layer.metrics if m.model not in names
    ]
    if problems:
        raise SemanticLayerError(
            "the semantic layer does not match the views:\n- " + "\n- ".join(problems)
        )
