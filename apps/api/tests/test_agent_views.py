from decimal import Decimal

import pytest
from psycopg import errors

from tests.money_month import money_month

pytestmark = pytest.mark.integration

TRANSACTIONS = [
    "booked_at",
    "month",
    "account",
    "bank",
    "amount",
    "direction",
    "tx_type",
    "spend",
    "income",
    "category",
    "category_group",
    "merchant",
    "bank_text",
    "bank_operation",
    "note",
    "is_subscription",
    "needs_review",
    "category_name",
    "group_name",
]
SUBSCRIPTIONS = [
    "merchant",
    "charges",
    "last_charge",
    "latest_amount",
    "cadence",
    "cadence_source",
    "monthly_equivalent",
    "active",
]


def _as_agent(db_conn) -> None:
    db_conn.execute("set local role agent_reader")
    db_conn.execute("set local search_path = agent")


def test_agent_views_expose_only_the_documented_columns(db_conn):
    rows = db_conn.execute(
        "select table_name, column_name from information_schema.columns"
        " where table_schema = 'agent' order by table_name, ordinal_position"
    ).fetchall()
    columns: dict[str, list[str]] = {}
    for row in rows:
        columns.setdefault(row["table_name"], []).append(row["column_name"])
    assert columns == {"subscriptions": SUBSCRIPTIONS, "transactions": TRANSACTIONS}


def test_agent_transactions_keep_the_money_rules_and_never_a_null_category(db_conn, make_tx):
    money_month(db_conn, make_tx)
    _as_agent(db_conn)
    rows = db_conn.execute(
        "select category, category_group, sum(spend) as spend from transactions"
        " where account = 'test 0077' and month = '1999-01' group by 1, 2"
    ).fetchall()
    by_category = {r["category"]: (r["category_group"], r["spend"]) for r in rows}
    assert by_category["uncategorized"] == ("uncategorized", Decimal("10.00"))
    assert by_category["fashion"] == ("shopping", Decimal("120.00"))
    assert by_category["loan_received"] == ("transfer", Decimal("0"))
    assert None not in by_category


def test_agent_transactions_name_categories_and_groups_as_the_app_does(db_conn, make_tx):
    money_month(db_conn, make_tx)
    _as_agent(db_conn)
    rows = db_conn.execute(
        "select distinct category, category_name, group_name from transactions"
        " where account = 'test 0077' and month = '1999-01'"
    ).fetchall()
    names = {r["category"]: (r["category_name"], r["group_name"]) for r in rows}
    assert names["fashion"] == ("Fashion", "Shopping")
    assert names["loan_received"] == ("Loan received", "Transfers")
    assert names["uncategorized"] == ("Uncategorized", "Uncategorized")


def test_agent_reader_reads_the_views_and_nothing_else(db_conn):
    _as_agent(db_conn)
    assert db_conn.execute("select count(*) as n from subscriptions").fetchone()["n"] >= 0
    with pytest.raises(errors.InsufficientPrivilege):
        db_conn.execute("select count(*) from public.accounts")


def test_deleting_a_thread_deletes_its_messages(db_conn):
    thread = db_conn.execute(
        "insert into chat_threads (title) values ('ZZTEST') returning id"
    ).fetchone()["id"]
    db_conn.execute(
        "insert into chat_messages (thread_id, role, content) values (%s, 'user', 'hi')", (thread,)
    )
    db_conn.execute("delete from chat_threads where id = %s", (thread,))
    count = db_conn.execute(
        "select count(*) as n from chat_messages where thread_id = %s", (thread,)
    ).fetchone()["n"]
    assert count == 0
