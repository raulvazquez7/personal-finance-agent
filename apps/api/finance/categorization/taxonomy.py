"""The two-level taxonomy: jev picks a level-2 slug, level 1 is derived (spec 5.1, 7)."""

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from psycopg import Connection
from pydantic import BaseModel

Direction = Literal["outgoing", "incoming"]
TxType = Literal["expense", "income", "transfer"]


class Category(BaseModel):
    slug: str
    tx_type: TxType
    level1: str
    what: str
    not_for: str | None = None


def direction_of(amount: Decimal) -> Direction:
    return "outgoing" if amount < 0 else "incoming"


class Taxonomy:
    def __init__(self, categories: list[Category]) -> None:
        self._by_slug = {category.slug: category for category in categories}

    def categories(self) -> list[Category]:
        return list(self._by_slug.values())

    def get(self, slug: str) -> Category:
        return self._by_slug[slug]

    def leaves(self, direction: Direction) -> list[Category]:
        """Options jev may pick: expense or income by direction, plus transfers."""
        kind = "expense" if direction == "outgoing" else "income"
        return [c for c in self._by_slug.values() if c.tx_type in (kind, "transfer")]

    def fits(self, slug: str, direction: Direction) -> bool:
        return any(category.slug == slug for category in self.leaves(direction))

    def level1_sums(self, probabilities: dict[str, float]) -> dict[str, float]:
        sums: dict[str, float] = defaultdict(float)
        for slug, probability in probabilities.items():
            sums[self._by_slug[slug].level1] += probability
        return {level1: round(total, 6) for level1, total in sums.items()}

    def tx_type_of(self, slug: str, amount: Decimal) -> TxType:
        if self._by_slug[slug].tx_type == "transfer":
            return "transfer"
        return "expense" if amount < 0 else "income"


def read_categories_yaml(path: Path) -> list[Category]:
    tree = yaml.safe_load(path.read_text())
    return [
        Category(slug=slug, tx_type=tx_type, level1=level1, **criterion)
        for tx_type, groups in tree.items()
        for level1, leaves in groups.items()
        for slug, criterion in leaves.items()
    ]


def load_taxonomy(conn: Connection) -> Taxonomy:
    rows = conn.execute(
        "select slug, tx_type, level1, what, not_for from categories order by position"
    ).fetchall()
    return Taxonomy([Category.model_validate(row) for row in rows])
