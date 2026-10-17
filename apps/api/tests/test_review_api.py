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


def _note(conn, tx):
    return conn.execute("select note from transactions where id = %s", (tx,)).fetchone()["note"]


def test_a_labelled_transaction_leaves_the_review_queue(client, db_conn, make_tx):
    tx = make_tx(
        "-4321.07", "ZZTEST UNKNOWN CODE", merchant="ZZTEST UNKNOWN CODE", booked_at=SYNTHETIC_DAY
    )
    _to_review(db_conn, tx, "uncategorized_expense")
    items = client.get("/review").json()
    assert f"t:{tx}" in {item["key"] for item in items}
    assert client.get("/review/count").json()["pending"] == len(items)

    response = client.post(
        f"/transactions/{tx}/label", json={"category_slug": "taxes", "is_subscription": False}
    )
    assert response.status_code == 204
    assert f"t:{tx}" not in _keys(client)


def test_the_count_includes_rows_no_run_has_categorized_yet(client, db_conn, make_tx):
    before = client.get("/review/count").json()
    make_tx("-9.90", "PAGO | ZZTEST NOT YET", merchant="ZZTEST NOT YET", booked_at=SYNTHETIC_DAY)
    after = client.get("/review/count").json()
    assert after == before | {"uncategorized": before["uncategorized"] + 1}


def test_a_refund_is_reviewed_with_its_merchant(client, db_conn, make_tx):
    acme = _merchant(db_conn, "ZZTEST ACME", category_slug="groceries")
    refund = make_tx("12.50", "DEVOLUCION | ZZTEST ACME", booked_at=SYNTHETIC_DAY)
    _to_review(db_conn, refund, "groceries", merchant_id=acme)
    keys = _keys(client)
    assert f"m:{acme}" in keys and f"t:{refund}" not in keys


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


def test_dismiss_merge(client, db_conn):
    foods = _merchant(db_conn, "ZZTEST ACME FOODS")
    other = _merchant(db_conn, "ZZTEST OTHER")
    db_conn.execute(
        "update merchants set merge_candidate_id = %s, merge_confidence = 0.6 where id = %s",
        (foods, other),
    )
    assert client.post(f"/merchants/{other}/dismiss-merge").status_code == 204
    row = db_conn.execute("select * from merchants where id = %s", (other,)).fetchone()
    assert row["confirmed"] and row["merge_candidate_id"] is None
    assert client.post(f"/merchants/{MISSING}/dismiss-merge").status_code == 404


def test_a_pending_merge_is_its_own_card_and_counted_apart(client, db_conn, make_tx):
    foods = _merchant(db_conn, "ZZTEST ACME FOODS")
    acme = _merchant(db_conn, "ZZTEST ACME")
    db_conn.execute(
        "update merchants set merge_candidate_id = %s, merge_confidence = 0.6 where id = %s",
        (foods, acme),
    )
    # A settled row of the source does not pull a category card in with the merge.
    settled = make_tx("-7.00", "PAGO | ZZTEST ACME", booked_at=SYNTHETIC_DAY)
    db_conn.execute(
        "update transactions set merchant_id = %s, category_source = 'jev',"
        " category_slug = 'groceries', needs_review = false where id = %s",
        (acme, settled),
    )
    cards = [
        item
        for item in client.get("/review").json()
        if item["merchant"] and item["merchant"]["id"] == str(acme)
    ]
    assert [(card["key"], card["kind"], card["transactions"]) for card in cards] == [
        (f"merge:{acme}", "merge", [])
    ]
    assert cards[0]["merge"]["merchant_id"] == str(foods)
    count = client.get("/review/count").json()
    assert count["pending"] == count["categories"] + count["merges"]
    assert count["merges"] >= 1 and "uncategorized" in count


def test_categories_and_merchant_autocomplete(client, db_conn):
    db_conn.execute("insert into merchants (name, match_key) values ('ZZTEST ACME', 'ZZTESTACME')")
    assert len(client.get("/categories").json()) == 57
    names = [m["name"] for m in client.get("/merchants", params={"q": "zztest"}).json()]
    assert names == ["ZZTEST ACME"]


def test_categories_carry_their_names_or_the_readable_slug(client, db_conn):
    def software():
        return next(c for c in client.get("/categories").json() if c["slug"] == "software_ai")

    assert (software()["name"], software()["group_name"]) == ("Software & AI", "Technology")
    db_conn.execute("update categories set name = null where slug = 'software_ai'")
    db_conn.execute("delete from category_groups where level1 = 'technology'")
    assert (software()["name"], software()["group_name"]) == ("Software ai", "Technology")


def test_label_rejects_an_income_category_for_money_out(client, make_tx):
    tx = make_tx("-3.00", "ZZTEST SHOP", booked_at=SYNTHETIC_DAY)
    body = {"category_slug": "salary", "is_subscription": False}
    assert client.post(f"/transactions/{tx}/label", json=body).status_code == 422


def test_note_and_default_endpoints(client, db_conn, make_tx):
    tx = make_tx("-3.00", "ZZTEST SHOP", booked_at=SYNTHETIC_DAY)
    assert client.patch(f"/transactions/{tx}", json={"note": "gift"}).status_code == 204
    assert client.patch(f"/transactions/{tx}", json={"note": "x" * 501}).status_code == 422
    assert client.patch(f"/transactions/{MISSING}", json={"note": "x"}).status_code == 404
    # The note field is required: an empty body is a 422 and leaves the note alone.
    assert client.patch(f"/transactions/{tx}", json={}).status_code == 422
    assert _note(db_conn, tx) == "gift"
    assert client.patch(f"/transactions/{tx}", json={"note": None}).status_code == 204
    assert _note(db_conn, tx) is None
    acme = _merchant(db_conn, "ZZTEST ACME", category_slug="groceries")
    assert client.delete(f"/merchants/{acme}/default").status_code == 204
    assert client.delete(f"/merchants/{MISSING}/default").status_code == 404
    # A real target: the old merge route would answer 204; with no route the path is 404.
    other = _merchant(db_conn, "ZZTEST OTHER")
    merge = client.post(f"/merchants/{acme}/merge", json={"into_id": str(other)})
    assert merge.status_code == 404


def test_a_confirm_without_a_subscription_answer_keeps_the_flag(client, db_conn):
    acme = _merchant(db_conn, "ZZTEST ACME", category_slug="groceries")
    db_conn.execute("update merchants set is_subscription = true where id = %s", (acme,))
    body = {"category_slug": "fashion"}
    # Required, like the note: leaving it out is a 422; null keeps the merchant's flag.
    assert client.post(f"/merchants/{acme}/review", json=body).status_code == 422
    kept = client.post(f"/merchants/{acme}/review", json={**body, "is_subscription": None})
    assert kept.status_code == 204
    row = db_conn.execute("select * from merchants where id = %s", (acme,)).fetchone()
    assert (row["category_slug"], row["is_subscription"]) == ("fashion", True)


def test_the_merchant_profile(client, db_conn, make_tx):
    acme = _merchant(db_conn, "ZZTEST ACME", category_slug="groceries")
    db_conn.execute("update merchants set is_subscription = true where id = %s", (acme,))
    for source in ("jev", "none", "user", "rule"):
        tx = make_tx("-9.90", f"PAGO | ZZTEST ACME {source}", booked_at=SYNTHETIC_DAY)
        db_conn.execute(
            "update transactions set merchant_id = %s, category_source = %s,"
            " is_subscription = %s where id = %s",
            (acme, source, source == "jev", tx),
        )
    assert client.get(f"/merchants/{acme}").json() == {
        "id": str(acme),
        "name": "ZZTEST ACME",
        "category_slug": "groceries",
        "is_subscription": True,
        "cadence": None,
        # One flagged charge is monthly in v_subscriptions.
        "cadence_effective": "monthly",
        "cadence_source": "auto",
        "rows_a_default_would_change": 2,
    }
    bare = _merchant(db_conn, "ZZTEST BARE")
    db_conn.execute("update merchants set cadence = 'yearly' where id = %s", (bare,))
    profile = client.get(f"/merchants/{bare}").json()
    assert (profile["cadence"], profile["cadence_effective"], profile["cadence_source"]) == (
        "yearly",
        None,
        None,
    )
    assert profile["rows_a_default_would_change"] == 0
    assert client.get(f"/merchants/{MISSING}").status_code == 404


def test_rename_or_merge_a_merchant(client, db_conn):
    acme = _merchant(db_conn, "ZZTEST ACME")
    other = _merchant(db_conn, "ZZTEST OTHER")
    both = {"name": "ZZTEST NEW", "merge_into_id": str(other)}
    for body in (both, {}, {"name": "!!!"}):
        assert client.patch(f"/merchants/{acme}", json=body).status_code == 422
    for body in ({"name": "ZZTEST NEW"}, {"merge_into_id": str(other)}):
        assert client.patch(f"/merchants/{MISSING}", json=body).status_code == 404

    renamed = client.patch(f"/merchants/{acme}", json={"name": "ZZTEST ACME RENAMED"})
    assert (renamed.status_code, renamed.json()) == (200, {"id": str(acme)})
    name = db_conn.execute("select name from merchants where id = %s", (acme,)).fetchone()["name"]
    assert name == "ZZTEST ACME RENAMED"

    merged = client.patch(f"/merchants/{acme}", json={"merge_into_id": str(other)})
    assert (merged.status_code, merged.json()) == (200, {"id": str(other)})
