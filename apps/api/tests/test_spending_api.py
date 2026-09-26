from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from finance.api.deps import db
from finance.api.main import app
from tests.money_month import IBAN, money_month

pytestmark = pytest.mark.integration


@pytest.fixture
def client(db_conn):
    previous = app.dependency_overrides.get(db)
    app.dependency_overrides[db] = lambda: db_conn
    yield TestClient(app)
    if previous is None:
        app.dependency_overrides.pop(db, None)
    else:
        app.dependency_overrides[db] = previous


def _detail(client, account, **params):
    base = {"account_id": str(account), "period": "month", "month": "1999-01"}
    response = client.get("/spending/detail", params={**base, **params})
    assert response.status_code == 200, response.text
    return response.json()


def _buckets_are_keys(body) -> bool:
    """Every stacked-bar bucket of every month is a series the web draws."""
    return all(set(m["by_child"]) <= set(body["child_keys"]) for m in body["months"])


def test_a_group_page_lists_its_categories_and_months(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    body = _detail(client, account, level1="shopping")
    assert body["total"] == "120.00" and body["count"] == 2
    assert [c["key"] for c in body["children"]] == ["fashion"]
    assert body["child_keys"] == ["fashion"]
    january = body["months"][-1]
    assert january == {
        "month": "1999-01",
        "has_data": True,
        "total": "120.00",
        "by_child": {"fashion": "120.00"},
    }
    assert len(body["latest"]) == 2
    assert _buckets_are_keys(body)


def test_a_category_page_lists_merchants_and_income_works_the_same(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    category = _detail(client, account, level1="shopping", category="fashion")
    assert (
        category["children"][0]["key"].startswith("category:")
        or category["children"][0]["merchant_id"]
    )
    income = _detail(client, account, type="income")
    assert income["total"] == "2000.00" and [c["key"] for c in income["children"]] == ["salary"]


def test_february_shows_a_negative_total_against_january(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    # Data up to February's last day: the whole of January is the comparison.
    make_tx("-10.00", "ZZTEST LAST DAY", iban=IBAN, booked_at=date(1999, 2, 28))
    body = _detail(client, account, level1="shopping", month="1999-02")
    assert (body["total"], body["previous_total"]) == ("-30.00", "120.00")
    assert body["cumulative"]["current"][-1]["total"] == "-30.00"


def test_a_detail_page_whose_data_ends_early_compares_with_as_many_days_before(
    client, db_conn, make_tx
):
    account = money_month(db_conn, make_tx)  # February's data ends on the 2nd
    body = _detail(client, account, level1="shopping", month="1999-02")
    assert body["period"]["previous_end"] == "1999-01-02"
    assert body["previous_total"] == "0"  # the January purchase came on the 3rd
    assert len(body["cumulative"]["previous"]) == len(body["cumulative"]["current"]) == 2


def test_a_child_seen_only_in_earlier_months_folds_into_a_listed_other(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    body = _detail(client, account, month="1999-02")  # February: only the fashion refund
    assert body["child_keys"] == ["fashion", "_other"]
    assert _buckets_are_keys(body)


def test_an_account_without_rows_has_no_cumulative_line(client):
    body = _detail(client, uuid4(), level1="shopping")
    assert body["total"] == "0" and body["period"]["latest_day"] is None
    assert body["cumulative"] == {"current": [], "previous": None}  # no data, never a 0 line


def test_a_merchant_page_has_no_children(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    merchant = db_conn.execute(
        "insert into merchants (name, match_key) values ('ZZTEST SHOP', 'zztestshop') returning id"
    ).fetchone()["id"]
    db_conn.execute(  # the two January fashion rows, not the February refund
        "update transactions set merchant_id = %s where account_id = %s"
        " and category_slug = 'fashion' and booked_at < '1999-02-01'",
        (merchant, account),
    )
    body = _detail(client, account, merchant_id=str(merchant))
    assert body["merchant_name"] == "ZZTEST SHOP"
    assert (body["total"], body["count"]) == ("120.00", 2)
    assert body["children"] == [] and body["child_keys"] == [] and body["top_merchants"] == []
    january = body["months"][-1]
    assert (january["month"], january["total"], january["by_child"]) == ("1999-01", "120.00", {})
