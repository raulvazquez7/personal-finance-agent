"""System rules: bank operations without a merchant, resolved before jev (spec 5)."""

from pathlib import Path
from typing import Literal

import yaml
from psycopg import Connection
from pydantic import BaseModel

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
