import pytest

from finance.categorization.seed import seed

pytestmark = pytest.mark.integration


def test_seed_disables_a_rule_removed_from_the_yaml(db_conn):
    db_conn.execute(
        "insert into rules (name, match_field, pattern, direction, category_slug)"
        " values ('zztest_gone', 'merchant', '^ZZTEST', 'any', 'groceries')"
    )
    seed(db_conn)
    row = db_conn.execute("select enabled from rules where name = 'zztest_gone'").fetchone()
    assert row["enabled"] is False
    kept = db_conn.execute(
        "select enabled, kind from rules where name = 'card_refund_concept'"
    ).fetchone()
    assert (kept["enabled"], kept["kind"]) == (True, "refund")


def test_seed_adds_the_slice_3_slugs(db_conn):
    seed(db_conn)
    rows = db_conn.execute(
        "select slug, tx_type, level1 from categories"
        " where slug in ('loan_received', 'credit_card_spending') order by slug"
    ).fetchall()
    assert [tuple(r.values()) for r in rows] == [
        ("credit_card_spending", "expense", "credit_card"),
        ("loan_received", "transfer", "transfer"),
    ]
