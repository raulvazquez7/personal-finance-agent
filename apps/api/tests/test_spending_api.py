import pytest
from fastapi.testclient import TestClient

from finance.api.deps import db
from finance.api.main import app
from tests.money_month import money_month

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
    return client.get("/spending/detail", params={**base, **params}).json()


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
    body = _detail(client, account, level1="shopping", month="1999-02")
    assert (body["total"], body["previous_total"]) == ("-30.00", "120.00")
    assert body["cumulative"]["current"][-1]["total"] == "-30.00"
