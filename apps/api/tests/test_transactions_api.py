from datetime import date

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


def _list(client, account, **params):
    base = {"account_id": str(account), "period": "month", "month": "1999-01"}
    return client.get("/transactions", params={**base, **params}).json()


def test_totals_cover_the_whole_filtered_set(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    body = _list(client, account)
    assert body["count"] == 11 and len(body["items"]) == 11
    assert (body["money_in"], body["money_out"]) == ("4590.00", "895.00")


def test_search_notes_and_saved_filters(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    db_conn.execute(
        "update transactions set note = %s where account_id = %s and amount = -200",
        ("100% wool_coat", account),
    )
    assert [i["note"] for i in _list(client, account, q="wool")["items"]] == ["100% wool_coat"]
    assert _list(client, account, q="100%")["count"] == 1
    assert _list(client, account, q="%")["count"] == 1  # literal percent, not a wildcard
    assert _list(client, account, q="_")["count"] == 1  # literal underscore, not a wildcard
    assert _list(client, account, saved="unpaired_own")["count"] == 1
    assert _list(client, account, saved="refunds")["count"] == 2  # fashion and Bizum back


def test_cursor_paging_never_skips_rows_on_the_same_day(client, db_conn, make_tx):
    for n in range(5):
        make_tx(f"-{n + 1}.00", f"ZZTEST SAME DAY {n}", iban=IBAN, booked_at=date(1999, 3, 9))
    account = db_conn.execute("select id from accounts where iban = %s", (IBAN,)).fetchone()["id"]
    seen, cursor = [], None
    for _ in range(5):  # 3 pages expected: a cursor that never advances fails, not hangs
        params = {"month": "1999-03", "limit": 2, **({"cursor": cursor} if cursor else {})}
        body = _list(client, account, **params)
        assert body["count"] == 5  # totals cover the whole filtered set on every page
        seen += [i["id"] for i in body["items"]]
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert cursor is None and len(seen) == len(set(seen)) == 5


@pytest.mark.parametrize(
    "cursor",
    ["2026-13-45_00000000-0000-0000-0000-000000000001", "2026-01-01_" + "-" * 36],
)
def test_a_cursor_that_does_not_parse_is_422(client, cursor):
    response = client.get("/transactions", params={"month": "1999-01", "cursor": cursor})
    assert response.status_code == 422


def test_card_numbers_are_masked(client, db_conn, make_tx):
    make_tx(
        "-9.90",
        "PAGO CON TARJETA | 4000123412341234 ZZTEST ACME",
        iban=IBAN,
        booked_at=date(1999, 4, 1),
    )
    account = db_conn.execute("select id from accounts where iban = %s", (IBAN,)).fetchone()["id"]
    [item] = _list(client, account, month="1999-04")["items"]
    assert item["description_raw"] == "PAGO CON TARJETA | •••• 1234 ZZTEST ACME"
