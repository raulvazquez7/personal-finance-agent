from datetime import date
from decimal import Decimal

import pytest

from finance.dashboard.breakdowns import breakdown, group_slots
from finance.dashboard.filters import Scope
from finance.dashboard.periods import Period
from tests.money_month import IBAN, money_month

pytestmark = pytest.mark.integration

JAN = Period(start=date(1999, 1, 1), end=date(1999, 1, 31))
FEB = Period(start=date(1999, 2, 1), end=date(1999, 2, 28))
MAR = Period(start=date(1999, 3, 1), end=date(1999, 3, 31))
APR = Period(start=date(1999, 4, 1), end=date(1999, 4, 30))


def test_groups_top_five_and_other(db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    scope = Scope(accounts=(account,), tx_type="expense")
    rows = breakdown(db_conn, "group", "spend", scope, JAN, None)
    by_key = {r.key: r for r in rows}
    assert by_key["credit_card"].amount == Decimal("175.00")
    assert by_key["shopping"].amount == Decimal("120.00")
    assert sum(r.amount for r in rows) == Decimal("455.00")
    assert all(r.previous is None for r in rows)
    assert len(rows) <= 6
    # January: credit_card 175 (1 row), financial 130 (1), shopping 120 (2), leisure 20 (2),
    # uncategorized 10 (1). With top=2 the last three fold into "_other".
    folded = breakdown(db_conn, "group", "spend", scope, JAN, None, top=2)
    assert [r.key for r in folded] == ["credit_card", "financial", "_other"]
    rest = folded[-1]
    assert (rest.amount, rest.folded, rest.count) == (Decimal("150.00"), 3, 5)


def _set_category(db_conn, tx, slug: str) -> None:
    db_conn.execute(
        "update transactions t set category_slug = c.slug, tx_type = c.tx_type,"
        " category_source = 'user' from categories c where c.slug = %s and t.id = %s",
        (slug, tx),
    )


def test_the_folded_tail_is_kept_on_the_other_row(db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    scope = Scope(accounts=(account,), tx_type="expense")
    own = {
        row.key: row.share
        for row in breakdown(db_conn, "group", "spend", scope, JAN, None, top=None)
    }
    folded = breakdown(db_conn, "group", "spend", scope, JAN, None, top=2)
    rest = folded[-1]
    # shopping 120, leisure 20, uncategorized 10: the tail, each with its own share.
    assert [row.key for row in rest.rows] == ["shopping", "leisure", "uncategorized"]
    assert [row.share for row in rest.rows] == [
        own["shopping"],
        own["leisure"],
        own["uncategorized"],
    ]

    # health exists only in March. April's fold must keep that amount on _other.previous
    # and must not invent a child row for a group the current period does not have.
    _set_category(
        db_conn,
        make_tx("-40.00", "ZZTEST PHARMACY", iban=IBAN, booked_at=date(1999, 3, 2)),
        "pharmacy",
    )
    for amount, slug, day in (
        ("-100.00", "credit_card_spending", date(1999, 4, 2)),
        ("-60.00", "loan_payment", date(1999, 4, 3)),
        ("-25.00", "fashion", date(1999, 4, 4)),
        ("-15.00", "restaurants_bars", date(1999, 4, 5)),
    ):
        _set_category(
            db_conn, make_tx(amount, f"ZZTEST APR {slug}", iban=IBAN, booked_at=day), slug
        )
    later = breakdown(db_conn, "group", "spend", scope, APR, MAR, top=2)
    other = later[-1]
    assert other.previous == Decimal("40.00")
    assert "health" not in {row.key for row in other.rows}


def test_a_merchant_with_two_categories_counts_both(db_conn, make_tx):
    iban = "ES0000000000000000000088"
    merchant = db_conn.execute(
        "insert into merchants (name, match_key) values ('ZZTEST DUAL', 'zztest-dual') returning id"
    ).fetchone()["id"]
    for amount, slug, day in (
        ("-12.00", "fashion", date(1999, 1, 4)),
        ("-8.00", "groceries", date(1999, 1, 5)),
    ):
        tx = make_tx(amount, f"ZZTEST DUAL {slug}", iban=iban, booked_at=day)
        db_conn.execute(
            "update transactions t set category_slug = c.slug, tx_type = c.tx_type,"
            " category_source = 'user', merchant_id = %s"
            " from categories c where c.slug = %s and t.id = %s",
            (merchant, slug, tx),
        )
    account = db_conn.execute("select id from accounts where iban = %s", (iban,)).fetchone()["id"]
    rows = breakdown(
        db_conn,
        "merchant",
        "spend",
        Scope(accounts=(account,), tx_type="expense"),
        JAN,
        None,
        top=None,
    )
    [row] = [item for item in rows if item.merchant_id == merchant]
    assert row.category_count == 2


def test_a_negative_group_is_kept_and_sorted_last(db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    dinner = make_tx("-15.00", "ZZTEST FEB DINNER", iban=IBAN, booked_at=date(1999, 2, 10))
    db_conn.execute(
        "update transactions set category_slug = 'restaurants_bars' where id = %s", (dinner,)
    )
    scope = Scope(accounts=(account,), tx_type="expense")
    rows = breakdown(db_conn, "group", "spend", scope, FEB, JAN)
    assert [(r.key, r.amount) for r in rows] == [
        ("leisure", Decimal("15.00")),
        ("shopping", Decimal("-30.00")),
    ]
    assert all(r.share == 0.0 for r in rows)  # the total is -15: no positive total to divide by
    assert rows[-1].previous == Decimal("120.00")


def test_merchants_without_a_merchant_fall_back_to_their_category(db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    rows = breakdown(
        db_conn,
        "merchant",
        "spend",
        Scope(accounts=(account,), tx_type="expense"),
        JAN,
        None,
        top=None,
    )
    assert "category:credit_card_spending" in {r.key for r in rows}


def test_group_slots_rank_all_time_spend(db_conn, make_tx):
    # Two synthetic rows whose spend dwarfs any real ledger take the first two slots.
    for amount, slug in (("-9000000000.00", "fashion"), ("-5000000000.00", "restaurants_bars")):
        tx = make_tx(amount, "ZZTEST BIG SPEND", iban=IBAN, booked_at=date(1999, 3, 1))
        db_conn.execute(
            "update transactions t set category_slug = c.slug, tx_type = c.tx_type,"
            " category_source = 'user' from categories c where c.slug = %s and t.id = %s",
            (slug, tx),
        )
    slots = group_slots(db_conn)
    assert sorted(slots.values()) == list(range(1, len(slots) + 1)) and len(slots) <= 5
    assert slots["shopping"] == 1 and slots["leisure"] == 2
