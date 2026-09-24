from datetime import date

import pytest
from fastapi.testclient import TestClient

from finance.api.deps import db
from finance.api.main import app

pytestmark = pytest.mark.integration

# The real ledger has no rows before 2000: assert only on these synthetic rows.
SYNTHETIC_DAY = date(1999, 1, 1)
MISSING = "00000000-0000-0000-0000-000000000009"


@pytest.fixture
def client(db_conn):
    previous = app.dependency_overrides.get(db)
    app.dependency_overrides[db] = lambda: db_conn
    yield TestClient(app)
    if previous is None:
        app.dependency_overrides.pop(db, None)
    else:
        app.dependency_overrides[db] = previous


def _merchant(conn, name, category_slug=None):
    return conn.execute(
        "insert into merchants (name, match_key, category_slug, confirmed)"
        " values (%s, %s, %s, %s) returning id",
        (
            name,
            "".join(ch for ch in name if ch.isalnum()),
            category_slug,
            category_slug is not None,
        ),
    ).fetchone()["id"]


def _to_review(conn, tx, category_slug, merchant_id=None):
    conn.execute(
        "update transactions set needs_review = true, category_source = 'jev',"
        " category_slug = %s, merchant_id = %s where id = %s",
        (category_slug, merchant_id, tx),
    )


def _keys(client):
    return {item["key"] for item in client.get("/review").json()}


def test_a_labelled_transaction_leaves_the_review_queue(client, db_conn, make_tx):
    tx = make_tx(
        "-4321.07", "ZZTEST UNKNOWN CODE", merchant="ZZTEST UNKNOWN CODE", booked_at=SYNTHETIC_DAY
    )
    _to_review(db_conn, tx, "uncategorized_expense")
    items = client.get("/review").json()
    assert f"t:{tx}" in {item["key"] for item in items}
    assert client.get("/review/count").json() == {"pending": len(items)}

    response = client.post(
        f"/transactions/{tx}/label", json={"category_slug": "taxes", "is_subscription": False}
    )
    assert response.status_code == 204
    assert f"t:{tx}" not in _keys(client)


def test_a_refund_of_a_merchant_with_an_expense_default_is_its_own_item(client, db_conn, make_tx):
    acme = _merchant(db_conn, "ZZTEST ACME", category_slug="groceries")
    refund = make_tx("12.50", "DEVOLUCION | ZZTEST ACME", booked_at=SYNTHETIC_DAY)
    _to_review(db_conn, refund, "refunds", merchant_id=acme)
    keys = _keys(client)
    assert f"t:{refund}" in keys and f"m:{acme}" not in keys


def test_unknown_category_and_unknown_merchant(client):
    bad = client.post(
        f"/merchants/{MISSING}/review", json={"category_slug": "nope", "is_subscription": False}
    )
    assert bad.status_code == 422
    gone = client.post(
        f"/merchants/{MISSING}/review",
        json={"category_slug": "groceries", "is_subscription": False},
    )
    assert gone.status_code == 404


def test_label_of_an_unknown_transaction_or_merchant_is_404(client, make_tx):
    tx = make_tx("-3.00", "ZZTEST SHOP", booked_at=SYNTHETIC_DAY)
    body = {"category_slug": "groceries", "is_subscription": False}
    assert client.post(f"/transactions/{MISSING}/label", json=body).status_code == 404
    unknown_merchant = {**body, "merchant_id": MISSING}
    assert client.post(f"/transactions/{tx}/label", json=unknown_merchant).status_code == 404


def test_a_merchant_name_without_letters_or_digits_is_422(client, db_conn, make_tx):
    acme = _merchant(db_conn, "ZZTEST ACME")
    tx = make_tx("-3.00", "ZZTEST SHOP", booked_at=SYNTHETIC_DAY)
    body = {"category_slug": "groceries", "is_subscription": False}
    rename = client.post(f"/merchants/{acme}/review", json={**body, "name": "!!!"})
    create = client.post(f"/transactions/{tx}/label", json={**body, "new_merchant_name": "!!!"})
    for response in (rename, create):
        assert response.status_code == 422 and "no letter" in response.json()["detail"]


def test_merge_and_dismiss_merge(client, db_conn):
    acme = _merchant(db_conn, "ZZTEST ACME")
    foods = _merchant(db_conn, "ZZTEST ACME FOODS")
    other = _merchant(db_conn, "ZZTEST OTHER")
    db_conn.execute(
        "update merchants set merge_candidate_id = %s, merge_confidence = 0.6 where id = %s",
        (foods, other),
    )
    assert client.post(f"/merchants/{acme}/merge", json={"into_id": str(foods)}).status_code == 204
    assert db_conn.execute("select 1 from merchants where id = %s", (acme,)).fetchone() is None
    assert client.post(f"/merchants/{other}/dismiss-merge").status_code == 204
    row = db_conn.execute("select * from merchants where id = %s", (other,)).fetchone()
    assert row["confirmed"] and row["merge_candidate_id"] is None

    assert (
        client.post(f"/merchants/{MISSING}/merge", json={"into_id": str(foods)}).status_code == 404
    )
    assert client.post(f"/merchants/{MISSING}/dismiss-merge").status_code == 404


def test_categories_and_merchant_autocomplete(client, db_conn):
    db_conn.execute("insert into merchants (name, match_key) values ('ZZTEST ACME', 'ZZTESTACME')")
    assert len(client.get("/categories").json()) == 55
    names = [m["name"] for m in client.get("/merchants", params={"q": "zztest"}).json()]
    assert names == ["ZZTEST ACME"]
