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


def test_group_slots_rank_all_time_spend(db_conn):
    slots = group_slots(db_conn)
    assert sorted(slots.values()) == list(range(1, len(slots) + 1)) and len(slots) <= 5
