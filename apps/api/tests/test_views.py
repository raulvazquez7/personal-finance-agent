from datetime import date
from decimal import Decimal

import pytest

from tests.money_month import money_month

pytestmark = pytest.mark.integration


def test_monthly_summary_follows_the_money_rules(db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    rows = db_conn.execute(
        "select month, income, expenses, savings from v_monthly_summary"
        " where account_id = %s order by month",
        (account,),
    ).fetchall()
    assert [tuple(r.values()) for r in rows] == [
        ("1999-01", Decimal("2000.00"), Decimal("455.00"), Decimal("1545.00")),
        ("1999-02", Decimal("0"), Decimal("-30.00"), Decimal("30.00")),
    ]


def test_spend_by_category_nets_refunds_and_keeps_uncategorized(db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    rows = db_conn.execute(
        "select category_slug, sum(spend) as spend from v_spend_by_category"
        " where account_id = %s and month = '1999-01'"
        " group by category_slug order by category_slug",
        (account,),
    ).fetchall()
    assert {r["category_slug"]: r["spend"] for r in rows} == {
        "credit_card_spending": Decimal("175.00"),
        "fashion": Decimal("120.00"),
        "loan_payment": Decimal("130.00"),
        "restaurants_bars": Decimal("20.00"),
        "uncategorized": Decimal("10.00"),
    }


def test_enriched_rows_carry_spend_income_and_note(db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    db_conn.execute(
        "update transactions set note = 'jacket' where account_id = %s and amount = -200",
        (account,),
    )
    row = db_conn.execute(
        "select spend, income, direction, level1, note from v_transactions_enriched"
        " where account_id = %s and amount = 80",
        (account,),
    ).fetchone()
    assert (row["spend"], row["income"], row["direction"], row["level1"]) == (
        Decimal("-80.00"),
        Decimal("0"),
        "incoming",
        "shopping",
    )
    jacket = db_conn.execute(
        "select note from v_transactions_enriched where account_id = %s and amount = -200",
        (account,),
    ).fetchone()
    assert jacket["note"] == "jacket"


def test_a_monthly_subscription_has_its_cadence_and_typical_amount(db_conn, make_tx):
    shop = db_conn.execute(
        "insert into merchants (name, match_key)"
        " values ('ZZTEST STREAM', 'ZZTESTSTREAM') returning id"
    ).fetchone()["id"]
    for day in (date(1999, 1, 3), date(1999, 2, 3), date(1999, 3, 3)):
        tx = make_tx("-9.99", "ZZTEST STREAM", booked_at=day)
        db_conn.execute(
            "update transactions set merchant_id = %s, is_subscription = true,"
            " category_slug = 'entertainment', tx_type = 'expense' where id = %s",
            (shop, tx),
        )
    row = db_conn.execute(
        "select cadence, typical_amount, monthly_equivalent, charges from v_subscriptions"
        " where merchant_id = %s",
        (shop,),
    ).fetchone()
    assert (row["cadence"], row["typical_amount"], row["monthly_equivalent"], row["charges"]) == (
        "monthly",
        Decimal("9.99"),
        Decimal("9.99"),
        3,
    )
