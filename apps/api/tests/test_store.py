import asyncio
import logging
from datetime import date

import pytest

from finance.categorization import store
from finance.categorization.labels import get_or_create_merchant
from finance.categorization.merchants import MerchantRoster
from finance.categorization.models import Categorization
from finance.categorization.store import categorize_pending, run_categorization_logged, save
from finance.settings import Settings
from tests.fakes import FakeJev, jev_result

ACME = jev_result(
    merchant={"ZZTEST ACME": 0.98, "none": 0.02},
    category={"groceries": 0.98, "restaurants_bars": 0.02},
)
# The real ledger has no rows before 2000, so its rows never compete with these.
SYNTHETIC_DAY = date(1999, 1, 1)
LOAN_CONTRACT = "0000-1111-22-3333334567"  # synthetic contract number, 4-4-2-10 digits


@pytest.fixture(autouse=True)
def no_real_jev(monkeypatch):
    """These tests see the real ledger (rolled back): a real jev client would bill every row."""

    def _refuse(*args, **kwargs):
        raise AssertionError("tests must pass a FakeJev or a Settings without a jev key")

    monkeypatch.setattr(store, "TypesafeJev", _refuse)


def _merchant_count(conn):
    return conn.execute(
        "select count(*) as n from merchants where match_key = 'ZZTESTACME'"
    ).fetchone()["n"]


def _source(conn, tx):
    row = conn.execute("select category_source from transactions where id = %s", (tx,))
    return row.fetchone()["category_source"]


@pytest.mark.integration
def test_categorize_saves_labels_and_one_merchant(db_conn, make_tx):
    tx = make_tx(
        "-9.90",
        "PAGO | ZZTEST ACME 0042",
        merchant="ZZTEST ACME 0042",
        bank_concept="PAGO CON TARJETA EN SUPERMERCADOS",
        booked_at=SYNTHETIC_DAY,
    )
    jev = FakeJev(first={"ZZTEST ACME 0042": ACME})
    asyncio.run(categorize_pending(db_conn, Settings(), jev=jev))
    row = db_conn.execute(
        "select category_slug, category_source, merchant_id, needs_review from transactions"
        " where id = %s",
        (tx,),
    ).fetchone()
    assert (row["category_slug"], row["category_source"], row["needs_review"]) == (
        "groceries",
        "jev",
        False,
    )
    assert row["merchant_id"] is not None and _merchant_count(db_conn) == 1
    label = db_conn.execute(
        "select source, model from transaction_labels where transaction_id = %s", (tx,)
    ).fetchone()
    assert (label["source"], label["model"]) == ("jev", "jev-test")


@pytest.mark.integration
def test_rerun_all_keeps_user_labels_and_does_not_duplicate_merchants(db_conn, make_tx):
    def tx(amount):
        return make_tx(
            amount, "PAGO | ZZTEST ACME 0042", merchant="ZZTEST ACME 0042", booked_at=SYNTHETIC_DAY
        )

    first, mine = tx("-9.90"), tx("-5.00")
    db_conn.execute(
        "update transactions set category_source = 'user', category_slug = 'fashion' where id = %s",
        (mine,),
    )
    jev = FakeJev(first={"ZZTEST ACME 0042": ACME})
    asyncio.run(categorize_pending(db_conn, Settings(), jev=jev))
    asyncio.run(categorize_pending(db_conn, Settings(), include_all=True, jev=jev))
    row = db_conn.execute(
        "select category_slug, category_source from transactions where id = %s", (mine,)
    ).fetchone()
    assert (row["category_slug"], row["category_source"]) == ("fashion", "user")
    assert _merchant_count(db_conn) == 1
    assert _source(db_conn, first) == "jev"


@pytest.mark.integration
def test_without_a_jev_key_rows_stay_pending_until_a_later_run(db_conn, make_tx):
    tx = make_tx("-9.90", "PAGO | ZZTEST ACME", merchant="ZZTEST ACME", booked_at=SYNTHETIC_DAY)
    summary = asyncio.run(categorize_pending(db_conn, Settings(typesafe_api_key=None)))
    assert summary.skipped
    assert _source(db_conn, tx) == "none"
    jev = FakeJev(first={"ZZTEST ACME": ACME})
    asyncio.run(categorize_pending(db_conn, Settings(), jev=jev))
    assert _source(db_conn, tx) == "jev"


@pytest.mark.integration
def test_a_row_jev_fails_on_stays_pending_while_the_others_are_saved(db_conn, make_tx):
    def tx(merchant, day):
        return make_tx(
            "-9.90", f"PAGO | {merchant}", merchant=merchant, booked_at=date(1999, 1, day)
        )

    ok, down, also_ok = tx("ZZTEST ACME", 1), tx("ZZTEST DOWN", 2), tx("ZZTEST ACME 2", 3)
    answers = {"ZZTEST ACME": ACME, "ZZTEST ACME 2": ACME}
    jev = FakeJev(first=answers | {"ZZTEST DOWN": RuntimeError("jev is down")})
    summary = asyncio.run(categorize_pending(db_conn, Settings(), jev=jev))
    assert summary.failed == 1
    assert [_source(db_conn, t) for t in (ok, down, also_ok)] == ["jev", "none", "jev"]
    later = FakeJev(first=answers | {"ZZTEST DOWN": ACME})
    asyncio.run(categorize_pending(db_conn, Settings(), jev=later))
    assert _source(db_conn, down) == "jev" and _merchant_count(db_conn) == 1


@pytest.mark.integration
def test_a_merge_suggestion_is_saved_on_the_new_merchant(db_conn, make_tx):
    make_tx("-9.90", "PAGO | ZZTEST ACME", merchant="ZZTEST ACME", booked_at=SYNTHETIC_DAY)
    make_tx(
        "-4.00",
        "PAGO | ZZTEST ACME ZZSHOP",
        merchant="ZZTEST ACME ZZSHOP",
        booked_at=date(1999, 1, 2),
    )
    shop = jev_result(
        merchant={"ZZTEST ACME ZZSHOP": 0.98, "none": 0.02}, category={"groceries": 0.98}
    )
    jev = FakeJev(
        first={"ZZTEST ACME": ACME, "ZZTEST ACME ZZSHOP": shop},
        same={"ZZTEST ACME ZZSHOP": jev_result(known={"ZZTEST ACME": 0.6, "none": 0.4})},
    )
    asyncio.run(categorize_pending(db_conn, Settings(), jev=jev))
    row = db_conn.execute(
        "select c.name as candidate, m.merge_confidence from merchants m"
        " join merchants c on c.id = m.merge_candidate_id where m.match_key = 'ZZTESTACMEZZSHOP'"
    ).fetchone()
    assert row["candidate"] == "ZZTEST ACME"
    assert row["merge_confidence"] == pytest.approx(0.6)


@pytest.mark.integration
def test_save_records_no_label_for_a_row_the_user_labelled_during_the_run(db_conn, make_tx):
    tx = make_tx("-9.90", "PAGO | ZZTEST ACME", booked_at=SYNTHETIC_DAY)
    result = Categorization(
        transaction_id=tx,
        tx_type="expense",
        category_slug="groceries",
        category_source="jev",
        category_confidence=0.99,
    )
    db_conn.execute(
        "update transactions set category_source = 'user', category_slug = 'fashion' where id = %s",
        (tx,),
    )
    save(db_conn, [result], MerchantRoster([]))
    assert _source(db_conn, tx) == "user"
    labels = db_conn.execute(
        "select count(*) as n from transaction_labels where transaction_id = %s", (tx,)
    ).fetchone()["n"]
    assert labels == 0


@pytest.mark.integration
def test_save_survives_merchants_merged_away_while_jev_was_answering(db_conn, make_tx):
    stale = get_or_create_merchant(db_conn, "ZZTEST STALE")
    gone = get_or_create_merchant(db_conn, "ZZTEST GONE")
    roster = store.load_roster(db_conn)
    roster.add("ZZTEST NEWSHOP")
    # The user merges both away in /review between the roster load and the save.
    db_conn.execute("delete from merchants where id = any(%s)", ([stale, gone],))
    known = make_tx("-9.90", "PAGO | ZZTEST STALE", booked_at=SYNTHETIC_DAY)
    new = make_tx("-4.00", "PAGO | ZZTEST NEWSHOP", booked_at=SYNTHETIC_DAY)

    def result(tx, merchant, **merge):
        return Categorization(
            transaction_id=tx,
            tx_type="expense",
            category_slug="groceries",
            category_source="jev",
            category_confidence=0.99,
            merchant_name=merchant,
            merchant_source="jev",
            **merge,
        )

    save(
        db_conn,
        [
            result(known, "ZZTEST STALE"),
            result(new, "ZZTEST NEWSHOP", merge_candidate_name="ZZTEST GONE", merge_confidence=0.6),
        ],
        roster,
    )
    saved = db_conn.execute(
        "select t.id, m.name, m.merge_candidate_id from transactions t"
        " join merchants m on m.id = t.merchant_id where t.id = any(%s)",
        ([known, new],),
    ).fetchall()
    by_tx = {row["id"]: row for row in saved}
    assert by_tx[known]["name"] == "ZZTEST STALE"  # recreated by name for its row
    assert (by_tx[new]["name"], by_tx[new]["merge_candidate_id"]) == ("ZZTEST NEWSHOP", None)
    assert [_source(db_conn, tx) for tx in (known, new)] == ["jev", "jev"]


def test_a_background_run_logs_a_failure_instead_of_raising(monkeypatch, caplog):
    def _fail(include_all=False):
        raise RuntimeError("jev is down")

    monkeypatch.setattr(store, "run_categorization", _fail)
    run_categorization_logged()
    assert "categorization failed" in caplog.text


def test_a_skipped_background_run_is_a_warning_so_the_api_console_shows_it(monkeypatch, caplog):
    skipped = store.CategorizeSummary(
        categorized=1, by_source={"rule": 1}, skipped="TYPESAFE_API_KEY is not set"
    )
    monkeypatch.setattr(store, "run_categorization", lambda include_all=False: skipped)
    run_categorization_logged()
    # The rules ran: only jev was skipped, and every count is printed.
    line = "jev skipped: TYPESAFE_API_KEY is not set (paired=0 categorized=1 rule=1 needs_review=0)"
    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [(logging.WARNING, line)]


def test_background_runs_hold_one_lock_so_they_never_overlap(monkeypatch):
    held = []

    def _run(include_all=False):
        held.append(store._run_lock.locked())
        return store.CategorizeSummary()

    monkeypatch.setattr(store, "run_categorization", _run)
    run_categorization_logged()
    assert held == [True] and not store._run_lock.locked()


@pytest.mark.integration
def test_without_a_jev_key_rules_still_apply(db_conn, make_tx):
    settlement = make_tx(
        "-175.00",
        "ADEUDO MENSUAL DE TARJETA | ZZTEST",
        bank_concept="ADEUDO MENSUAL DE TARJETA",
        booked_at=SYNTHETIC_DAY,
    )
    shop = make_tx("-9.90", "PAGO | ZZTEST ACME", merchant="ZZTEST ACME", booked_at=SYNTHETIC_DAY)
    repayment = "CARGO POR AMORTIZACION DE PRESTAMO/CREDITO"
    loan = make_tx(
        "-130.00", f"{repayment} | {LOAN_CONTRACT}", bank_concept=repayment, booked_at=SYNTHETIC_DAY
    )
    summary = asyncio.run(categorize_pending(db_conn, Settings(typesafe_api_key=None)))
    assert summary.skipped and summary.by_source.get("rule", 0) >= 1
    assert summary.line().startswith("jev skipped: TYPESAFE_API_KEY is not set (paired=")
    assert _source(db_conn, settlement) == "rule"
    assert _source(db_conn, shop) == "none"
    # The run links the loan row to its contract's merchant (link_loans).
    name = db_conn.execute(
        "select m.name from transactions t join merchants m on m.id = t.merchant_id"
        " where t.id = %s",
        (loan,),
    ).fetchone()
    assert name is not None and name["name"] == "Loan ····4567"


@pytest.mark.integration
def test_a_rules_only_run_never_calls_jev(db_conn, make_tx):
    make_tx("-9.90", "PAGO | ZZTEST ACME", merchant="ZZTEST ACME", booked_at=SYNTHETIC_DAY)
    jev = FakeJev()
    asyncio.run(categorize_pending(db_conn, Settings(), jev=jev, rules_only=True))
    assert jev.calls == []
