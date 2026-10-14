from datetime import date, timedelta
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
        "select cadence, latest_amount, monthly_equivalent, charges from v_subscriptions"
        " where merchant_id = %s",
        (shop,),
    ).fetchone()
    assert (row["cadence"], row["latest_amount"], row["monthly_equivalent"], row["charges"]) == (
        "monthly",
        Decimal("9.99"),
        Decimal("9.99"),
        3,
    )


def test_a_yearly_subscription_costs_a_twelfth_per_month(db_conn, make_tx):
    shop = db_conn.execute(
        "insert into merchants (name, match_key)"
        " values ('ZZTEST YEARLY', 'ZZTESTYEARLY') returning id"
    ).fetchone()["id"]
    for day in (date(1999, 1, 10), date(1999, 12, 10)):  # a 334-day gap: over 200 is yearly
        tx = make_tx("-120.00", "ZZTEST YEARLY", booked_at=day)
        db_conn.execute(
            "update transactions set merchant_id = %s, is_subscription = true,"
            " category_slug = 'software_ai', tx_type = 'expense' where id = %s",
            (shop, tx),
        )
    row = db_conn.execute(
        "select cadence, latest_amount, monthly_equivalent, charges from v_subscriptions"
        " where merchant_id = %s",
        (shop,),
    ).fetchone()
    assert (row["cadence"], row["latest_amount"], row["monthly_equivalent"], row["charges"]) == (
        "yearly",
        Decimal("120.00"),
        Decimal("10.00"),
        2,
    )


def test_a_charge_every_91_days_is_quarterly_at_a_third_of_the_latest_charge(db_conn, make_tx):
    shop = db_conn.execute(
        "insert into merchants (name, match_key)"
        " values ('ZZTEST QUARTER', 'ZZTESTQUARTER') returning id"
    ).fetchone()["id"]
    for day, amount in (
        (date(1999, 1, 1), "-30.00"),
        (date(1999, 4, 2), "-60.00"),  # 91 days, and the later price
    ):
        tx = make_tx(amount, "ZZTEST QUARTER", booked_at=day)
        db_conn.execute(
            "update transactions set merchant_id = %s, is_subscription = true,"
            " category_slug = 'entertainment', tx_type = 'expense' where id = %s",
            (shop, tx),
        )
    row = db_conn.execute(
        "select cadence, cadence_source, latest_amount, monthly_equivalent, active"
        " from v_subscriptions where merchant_id = %s",
        (shop,),
    ).fetchone()
    assert (
        row["cadence"],
        row["cadence_source"],
        row["latest_amount"],
        row["monthly_equivalent"],
    ) == ("quarterly", "auto", Decimal("60.00"), Decimal("20.00"))


def test_a_manual_cadence_beats_the_gap_and_can_be_cleared(db_conn, make_tx):
    shop = db_conn.execute(
        "insert into merchants (name, match_key, cadence)"
        " values ('ZZTEST PIN', 'ZZTESTPIN', 'yearly') returning id"
    ).fetchone()["id"]
    for day in (date(1999, 1, 3), date(1999, 2, 3)):
        tx = make_tx("-12.00", "ZZTEST PIN", booked_at=day)
        db_conn.execute(
            "update transactions set merchant_id = %s, is_subscription = true,"
            " category_slug = 'entertainment', tx_type = 'expense' where id = %s",
            (shop, tx),
        )
    pinned = db_conn.execute(
        "select cadence, cadence_source, monthly_equivalent from v_subscriptions"
        " where merchant_id = %s",
        (shop,),
    ).fetchone()
    assert (pinned["cadence"], pinned["cadence_source"], pinned["monthly_equivalent"]) == (
        "yearly",
        "user",
        Decimal("1.00"),
    )
    db_conn.execute("update merchants set cadence = null where id = %s", (shop,))
    cleared = db_conn.execute(
        "select cadence, cadence_source from v_subscriptions where merchant_id = %s", (shop,)
    ).fetchone()
    assert (cleared["cadence"], cleared["cadence_source"]) == ("monthly", "auto")


def test_the_larger_charge_of_the_latest_day_is_the_latest_amount(db_conn, make_tx):
    shop = db_conn.execute(
        "insert into merchants (name, match_key)"
        " values ('ZZTEST SAMEDAY', 'ZZTESTSAMEDAY') returning id"
    ).fetchone()["id"]
    for day, amount in (
        (date(1999, 1, 5), "-50.00"),
        (date(1999, 2, 5), "-7.00"),
        (date(1999, 2, 5), "-12.00"),
    ):
        tx = make_tx(amount, "ZZTEST SAMEDAY", booked_at=day)
        db_conn.execute(
            "update transactions set merchant_id = %s, is_subscription = true,"
            " category_slug = 'entertainment', tx_type = 'expense' where id = %s",
            (shop, tx),
        )
    row = db_conn.execute(
        "select latest_amount from v_subscriptions where merchant_id = %s", (shop,)
    ).fetchone()
    assert row["latest_amount"] == Decimal("12.00")


def _anchored_subscription(db_conn, make_tx, name, days_before_latest):
    """Charges counted back from the ledger's latest day. An anchor row on that day keeps the
    latest day fixed when the ledger is empty."""
    latest = db_conn.execute("select max(booked_at) as d from transactions").fetchone()["d"]
    latest = latest or date(1999, 12, 31)
    make_tx("-1.00", "ZZTEST ANCHOR", booked_at=latest)
    shop = db_conn.execute(
        "insert into merchants (name, match_key) values (%s, %s) returning id",
        (name, name.replace(" ", "")),
    ).fetchone()["id"]
    for days in days_before_latest:
        tx = make_tx("-30.00", name, booked_at=latest - timedelta(days=days))
        db_conn.execute(
            "update transactions set merchant_id = %s, is_subscription = true,"
            " category_slug = 'entertainment', tx_type = 'expense' where id = %s",
            (shop, tx),
        )
    return shop


def test_a_quarterly_plan_stays_active_for_120_days(db_conn, make_tx):
    # 80 days after its last charge: out of the monthly 45-day window, inside the quarterly one.
    running = _anchored_subscription(db_conn, make_tx, "ZZTEST QRUNNING", (171, 80))
    # 130 days after its last charge: past the quarterly window too.
    ended = _anchored_subscription(db_conn, make_tx, "ZZTEST QENDED", (221, 130))
    rows = {
        r["merchant_id"]: (r["cadence"], r["active"])
        for r in db_conn.execute(
            "select merchant_id, cadence, active from v_subscriptions where merchant_id = any(%s)",
            ([running, ended],),
        ).fetchall()
    }
    assert rows == {running: ("quarterly", True), ended: ("quarterly", False)}
