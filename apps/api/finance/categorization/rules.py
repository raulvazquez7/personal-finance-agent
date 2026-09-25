"""System rules: bank operations without a merchant, resolved before jev (spec 5)."""

import re
from pathlib import Path
from typing import Literal

import yaml
from psycopg import Connection
from pydantic import BaseModel, field_validator, model_validator

from finance.categorization.taxonomy import Direction
from finance.models import Bank


class Rule(BaseModel):
    name: str
    bank: Bank | None = None
    match_field: Literal["bank_concept", "merchant"]
    pattern: str
    direction: Literal["outgoing", "incoming", "any"]
    kind: Literal["categorize", "refund"] = "categorize"
    category_slug: str | None = None

    @field_validator("pattern")
    @classmethod
    def _compiles(cls, pattern: str) -> str:
        # A bad regex fails at load, not on the first matching row. re.error is not a
        # ValueError, so pydantic would not turn it into a ValidationError on its own.
        try:
            re.compile(pattern)
        except re.error as error:
            raise ValueError(f"invalid pattern {pattern!r}: {error}") from error
        return pattern

    @model_validator(mode="after")
    def _slug_matches_kind(self) -> "Rule":
        if (self.kind == "categorize") != (self.category_slug is not None):
            raise ValueError(
                f"rule {self.name}: a categorize rule needs a category, a refund rule has none"
            )
        return self


def read_rules_yaml(path: Path) -> list[Rule]:
    return [Rule.model_validate(item) for item in yaml.safe_load(path.read_text(encoding="utf-8"))]


def load_rules(conn: Connection) -> list[Rule]:
    rows = conn.execute(
        "select name, bank, match_field, pattern, direction, kind, category_slug from rules"
        " where enabled order by name"
    ).fetchall()
    return [Rule.model_validate(row) for row in rows]


def _matches(
    rule: Rule, bank: Bank, bank_concept: str | None, merchant: str | None, direction: Direction
) -> bool:
    if rule.bank not in (None, bank) or rule.direction not in ("any", direction):
        return False
    text = bank_concept if rule.match_field == "bank_concept" else merchant
    return bool(text and re.search(rule.pattern, text, re.IGNORECASE))


def match_rule(
    rules: list[Rule],
    bank: Bank,
    bank_concept: str | None,
    merchant: str | None,
    direction: Direction,
) -> Rule | None:
    for rule in rules:
        if rule.kind == "categorize" and _matches(rule, bank, bank_concept, merchant, direction):
            return rule
    return None


def is_refund(
    rules: list[Rule],
    bank: Bank,
    bank_concept: str | None,
    merchant: str | None,
    direction: Direction,
) -> bool:
    """A card purchase coming back (spec 2.2): jev then sees expense categories."""
    return any(
        rule.kind == "refund" and _matches(rule, bank, bank_concept, merchant, direction)
        for rule in rules
    )
