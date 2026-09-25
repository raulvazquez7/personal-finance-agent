from decimal import Decimal
from uuid import uuid4

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


def _overview(client, account, **params):
    return client.get("/dashboard/overview", params={"account_id": str(account), **params}).json()


def test_overview_kpis_and_breakdowns_follow_the_money_rules(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    body = _overview(client, account, period="month", month="1999-01")
    assert body["kpis"] == {
        "income": "2000.00",
        "expenses": "455.00",
        "savings": "1545.00",
        "savings_rate": 0.7725,
    }
    assert body["period"]["has_previous"] is False
    assert body["previous_kpis"] is None
    assert sum(Decimal(r["amount"]) for r in body["by_group"]) == Decimal("455.00")
    assert len(body["months"]) == 12 and body["months"][-1] == {
        "month": "1999-01",
        "has_data": True,
        "income": "2000.00",
        "expenses": "455.00",
        "savings": "1545.00",
    }
    assert body["months"][0]["has_data"] is False
    last = body["cumulative"]["current"][-1]
    assert (last["day"], last["total"]) == (31, "455.00")


def test_february_compares_with_january(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    body = _overview(client, account, period="month", month="1999-02")
    assert body["period"]["has_previous"] is True
    assert body["previous_kpis"]["expenses"] == "455.00"
    assert body["kpis"]["savings_rate"] is None  # no income in February
    assert body["cumulative"]["previous"][-1]["total"] == "455.00"


def test_an_account_without_rows_returns_an_empty_overview(client):
    body = _overview(client, uuid4())
    assert body["kpis"]["expenses"] == "0" and body["period"]["has_previous"] is False
    assert all(not m["has_data"] for m in body["months"])
    assert body["by_group"] == []


def test_a_bad_custom_range_is_422(client):
    response = client.get(
        "/dashboard/overview",
        params={"period": "custom", "start": "1999-02-01", "end": "1999-01-01"},
    )
    assert response.status_code == 422


def test_a_month_13_is_422(client):
    assert client.get("/dashboard/overview", params={"month": "1999-13"}).status_code == 422


def test_subscriptions_endpoint_returns_totals(client):
    body = client.get("/dashboard/subscriptions").json()
    assert Decimal(body["yearly_total"]) == Decimal(body["monthly_total"]) * 12
