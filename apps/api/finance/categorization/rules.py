"""System rules: bank operations without a merchant, resolved before jev (spec 5)."""

import re
from pathlib import Path
from typing import Literal

import yaml
from psycopg import Connection
from pydantic import BaseModel

from finance.categorization.taxonomy import Direction
from finance.models import Bank


class Rule(BaseModel):
    name: str
    bank: Bank | None = None
    match_field: Literal["bank_concept", "merchant"]
    pattern: str
    direction: Literal["outgoing", "incoming", "any"]
    category_slug: str


def read_rules_yaml(path: Path) -> list[Rule]:
    return [Rule.model_validate(item) for item in yaml.safe_load(path.read_text())]


def load_rules(conn: Connection) -> list[Rule]:
    rows = conn.execute(
        "select name, bank, match_field, pattern, direction, category_slug from rules"
        " where enabled order by name"
    ).fetchall()
    return [Rule.model_validate(row) for row in rows]


def match_rule(
    rules: list[Rule],
    bank: Bank,
    bank_concept: str | None,
    merchant: str | None,
    direction: Direction,
) -> Rule | None:
    for rule in rules:
        if rule.bank not in (None, bank) or rule.direction not in ("any", direction):
            continue
        text = bank_concept if rule.match_field == "bank_concept" else merchant
        if text and re.search(rule.pattern, text, re.IGNORECASE):
            return rule
    return None
