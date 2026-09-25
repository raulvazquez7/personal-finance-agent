from datetime import date
from uuid import uuid4

import pytest

from finance.categorization.labels import (
    NotFound,
    confirm_merchant,
    dismiss_merge,
    get_or_create_merchant,
    label_transaction,
    merge_merchants,
)

pytestmark = pytest.mark.integration

# The real ledger has no rows before 2000, so its rows never compete with these.
SYNTHETIC_DAY = date(1999, 1, 1)


def _merchant(conn, name, **columns):
    row = conn.execute(
        "insert into merchants (name, match_key) values (%s, %s) returning id",
        (name, "".join(ch for ch in name.upper() if ch.isalnum())),
    ).fetchone()
    for column, value in columns.items():
        conn.execute(f"update merchants set {column} = %s where id = %s", (value, row["id"]))
    return row["id"]


def _tx(make_tx, amount, description_raw):
    return make_tx(amount, description_raw, booked_at=SYNTHETIC_DAY)


def _set(conn, tx, **columns):
    for column, value in columns.items():
        conn.execute(f"update transactions set {column} = %s where id = %s", (value, tx))


def _row(conn, tx):
    return conn.execute("select * from transactions where id = %s", (tx,)).fetchone()


def test_confirm_sets_the_default_and_relabels_reviewed_rows(db_conn, make_tx):
    acme = _merchant(db_conn, "ZZTEST ACME")
    charge = _tx(make_tx, "-9.90", "PAGO | ZZTEST ACME")
    refund = _tx(make_tx, "9.90", "DEVOLUCION | ZZTEST ACME")
    mine = _tx(make_tx, "-5.00", "PAGO | ZZTEST ACME")
    _set(
        db_conn,
        charge,
        merchant_id=acme,
        category_source="jev",
        category_slug="groceries",
        needs_review=True,
    )
    _set(db_conn, refund, merchant_id=acme, category_source="jev", category_slug="refunds")
    _set(db_conn, mine, merchant_id=acme, category_source="user", category_slug="fashion")

    confirm_merchant(db_conn, acme, "restaurants_bars", False)

    assert (_row(db_conn, charge)["category_slug"], _row(db_conn, charge)["category_source"]) == (
        "restaurants_bars",
        "merchant",
    )
    assert _row(db_conn, charge)["needs_review"] is False
    refund_row = _row(db_conn, refund)
    assert (refund_row["category_slug"], refund_row["tx_type"]) == ("restaurants_bars", "expense")
    assert _row(db_conn, mine)["category_slug"] == "fashion"
    merchant = db_conn.execute("select * from merchants where id = %s", (acme,)).fetchone()
    assert (merchant["category_slug"], merchant["confirmed"]) == ("restaurants_bars", True)
    label = db_conn.execute(
        "select source from transaction_labels where transaction_id = %s", (charge,)
    ).fetchone()
    assert label["source"] == "user"


def test_confirm_relabels_pending_rows_and_leaves_rule_rows(db_conn, make_tx):
    acme = _merchant(db_conn, "ZZTEST ACME")
    pending = _tx(make_tx, "-9.90", "PAGO | ZZTEST ACME")
    ruled = _tx(make_tx, "-20.00", "TRASPASO | ZZTEST ACME")
    _set(db_conn, pending, merchant_id=acme)
    _set(db_conn, ruled, merchant_id=acme, category_source="rule", category_slug="own_accounts")

    confirm_merchant(db_conn, acme, "groceries", False)

    assert _row(db_conn, pending)["category_source"] == "merchant"
    assert _row(db_conn, ruled)["category_slug"] == "own_accounts"


def test_subscriptions_stay_on_expenses(db_conn, make_tx):
    broker = _merchant(db_conn, "ZZTEST BROKER")
    deposit = _tx(make_tx, "-50.00", "TRASPASO | ZZTEST BROKER")
    one_off = _tx(make_tx, "-50.00", "TRASPASO | ZZTEST BROKER")
    _set(db_conn, deposit, merchant_id=broker, category_source="jev", category_slug="fashion")

    confirm_merchant(db_conn, broker, "savings_investment", True)
    label_transaction(db_conn, one_off, "own_accounts", True)

    for tx in (deposit, one_off):
        assert (_row(db_conn, tx)["tx_type"], _row(db_conn, tx)["is_subscription"]) == (
            "transfer",
            False,
        )
        label = db_conn.execute(
            "select is_subscription from transaction_labels where transaction_id = %s", (tx,)
        ).fetchone()
        assert label["is_subscription"] is False


def test_one_off_label_creates_a_merchant_and_leaves_defaults_alone(db_conn, make_tx):
    acme = _merchant(db_conn, "ZZTEST ACME", category_slug="groceries")
    tx = _tx(make_tx, "-30.00", "PAGO | ZZTEST ACME")
    _set(db_conn, tx, merchant_id=acme, category_source="merchant", category_slug="groceries")

    label_transaction(db_conn, tx, "home_goods", False, new_merchant_name="ZZTEST ACME HOME")

    row = _row(db_conn, tx)
    assert (row["category_slug"], row["category_source"], row["merchant_source"]) == (
        "home_goods",
        "user",
        "user",
    )
    assert row["merchant_id"] != acme
    default = db_conn.execute("select category_slug from merchants where id = %s", (acme,))
    assert default.fetchone()["category_slug"] == "groceries"


def test_one_off_label_with_an_unknown_merchant_is_not_found(db_conn, make_tx):
    tx = _tx(make_tx, "-30.00", "PAGO | ZZTEST ACME")
    with pytest.raises(NotFound):
        label_transaction(db_conn, tx, "home_goods", False, merchant_id=uuid4())


def test_get_or_create_merchant_reuses_the_key(db_conn):
    acme = get_or_create_merchant(db_conn, "  ZZTEST ACME ")
    assert get_or_create_merchant(db_conn, "zztest acme") == acme
    name = db_conn.execute("select name from merchants where id = %s", (acme,))
    assert name.fetchone()["name"] == "ZZTEST ACME"


@pytest.mark.parametrize("name", ["-- !!", "ÉÑ"])
def test_a_name_without_a_match_key_is_refused(db_conn, make_tx, name):
    """match_key keeps A-Z and digits only; an empty key would land on another merchant."""
    acme = _merchant(db_conn, "ZZTEST ACME")
    tx = _tx(make_tx, "-9.90", "PAGO | ZZTEST ACME")
    with pytest.raises(ValueError):
        get_or_create_merchant(db_conn, name)
    with pytest.raises(ValueError):
        label_transaction(db_conn, tx, "groceries", False, new_merchant_name=name)
    with pytest.raises(ValueError):
        confirm_merchant(db_conn, acme, "groceries", False, name=name)


def test_merge_repoints_rows_and_keeps_the_target_default(db_conn, make_tx):
    source = _merchant(db_conn, "ZZTEST ACME FOODS", category_slug="fashion")
    target = _merchant(db_conn, "ZZTEST ACME", category_slug="groceries")
    tx = _tx(make_tx, "-9.90", "PAGO | ZZTEST ACME FOODS")
    _set(db_conn, tx, merchant_id=source)

    merge_merchants(db_conn, source, target)

    assert _row(db_conn, tx)["merchant_id"] == target
    assert db_conn.execute("select 1 from merchants where id = %s", (source,)).fetchone() is None
    kept = db_conn.execute("select category_slug from merchants where id = %s", (target,))
    assert kept.fetchone()["category_slug"] == "groceries"


def test_renaming_to_an_existing_merchant_merges(db_conn, make_tx):
    source = _merchant(db_conn, "ZZTEST ACME 2")
    target = _merchant(db_conn, "ZZTEST ACME")
    tx = _tx(make_tx, "-9.90", "PAGO | ZZTEST ACME 2")
    _set(db_conn, tx, merchant_id=source, category_source="jev", category_slug="fashion")

    holder = confirm_merchant(db_conn, source, "groceries", False, name="zztest acme")

    assert holder == target and _row(db_conn, tx)["merchant_id"] == target


def test_dismiss_merge_confirms_the_merchant(db_conn):
    target = _merchant(db_conn, "ZZTEST ACME")
    source = _merchant(db_conn, "ZZTEST ACME BAR", merge_candidate_id=target, merge_confidence=0.6)
    dismiss_merge(db_conn, source)
    row = db_conn.execute("select * from merchants where id = %s", (source,)).fetchone()
    assert (row["confirmed"], row["merge_candidate_id"]) == (True, None)


def test_a_money_in_row_labelled_with_an_expense_category_is_a_negative_expense(db_conn, make_tx):
    refund = _tx(make_tx, "80.00", "DEVOLUCION | ZZTEST SHOP")
    label_transaction(db_conn, refund, "fashion", is_subscription=True)
    row = _row(db_conn, refund)
    assert (row["tx_type"], row["is_subscription"]) == ("expense", False)
