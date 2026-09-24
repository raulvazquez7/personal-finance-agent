"""Upsert the taxonomy and system rules from supabase/seed (run after every migration)."""

from psycopg import Connection

from finance.categorization.rules import read_rules_yaml
from finance.categorization.taxonomy import read_categories_yaml
from finance.settings import REPO_ROOT

SEED_DIR = REPO_ROOT / "supabase" / "seed"


def seed(conn: Connection) -> tuple[int, int]:
    categories = read_categories_yaml(SEED_DIR / "categories.yaml")
    rules = read_rules_yaml(SEED_DIR / "rules.yaml")
    with conn.transaction():
        for position, c in enumerate(categories):
            conn.execute(
                "insert into categories (slug, tx_type, level1, what, not_for, position)"
                " values (%s, %s, %s, %s, %s, %s) on conflict (slug) do update set"
                " tx_type = excluded.tx_type, level1 = excluded.level1,"
                " what = excluded.what, not_for = excluded.not_for, position = excluded.position",
                (c.slug, c.tx_type, c.level1, c.what, c.not_for, position),
            )
        for r in rules:
            conn.execute(
                "insert into rules (name, bank, match_field, pattern, direction, category_slug)"
                " values (%s, %s, %s, %s, %s, %s) on conflict (name) do update set"
                " bank = excluded.bank, match_field = excluded.match_field,"
                " pattern = excluded.pattern, direction = excluded.direction,"
                " category_slug = excluded.category_slug",
                (r.name, r.bank, r.match_field, r.pattern, r.direction, r.category_slug),
            )
    return len(categories), len(rules)
