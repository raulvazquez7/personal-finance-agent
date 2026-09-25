from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from finance.categorization.pairing import PairCandidate, find_pairs, pair_transfers
from finance.settings import Settings

PATTERN = "TRASPASO|TRANSFER|BIZUM|TRF"
A, B, C = uuid4(), uuid4(), uuid4()


def _tx(account, amount, text="TRASPASO", day=1):
    return PairCandidate(
        id=uuid4(),
        account_id=account,
        booked_at=date(2026, 7, day),
        amount=Decimal(amount),
        description_raw=text,
    )


def test_pairs_opposite_amounts_between_accounts():
    out, into = _tx(A, "-300"), _tx(B, "300", day=2)
    assert find_pairs([out, into], PATTERN, 2) == [(out.id, into.id)]


def test_same_account_is_not_a_transfer_pair():
    assert find_pairs([_tx(A, "-300"), _tx(A, "300")], PATTERN, 2) == []


def test_outside_the_window_is_not_paired():
    assert find_pairs([_tx(A, "-300", day=1), _tx(B, "300", day=4)], PATTERN, 2) == []


def test_exactly_window_days_apart_pairs():
    out, into = _tx(A, "-300", day=1), _tx(B, "300", day=3)
    assert find_pairs([out, into], PATTERN, 2) == [(out.id, into.id)]


def test_different_amounts_do_not_pair():
    assert find_pairs([_tx(A, "-300"), _tx(B, "299")], PATTERN, 2) == []


def test_pattern_is_case_insensitive():
    out, into = _tx(A, "-300", "traspaso a ahorro"), _tx(B, "300", "Transferencia recibida")
    assert find_pairs([out, into], PATTERN, 2) == [(out.id, into.id)]


def test_card_purchases_never_pair():
    out, into = _tx(A, "-20", "PAGO CON TARJETA | ACME"), _tx(B, "20", "DEVOLUCION ACME")
    assert find_pairs([out, into], PATTERN, 2) == []


def test_pairing_is_one_to_one_and_prefers_the_nearest_date():
    out = _tx(A, "-50", "BIZUM ENVIADO", day=3)
    far, near = _tx(B, "50", "BIZUM RECIBIDO", day=1), _tx(C, "50", "BIZUM RECIBIDO", day=3)
    second_out = _tx(A, "-50", "BIZUM ENVIADO", day=4)
    pairs = find_pairs([out, far, near, second_out], PATTERN, 2)
    assert pairs == [(out.id, near.id)]


def test_an_earlier_outgoing_row_does_not_take_a_nearer_rows_counterpart():
    external = _tx(A, "-20", "BIZUM ENVIADO", day=1)
    household = _tx(C, "-20", "BIZUM ENVIADO", day=3)
    received = _tx(B, "20", "BIZUM RECIBIDO", day=3)
    assert find_pairs([external, household, received], PATTERN, 2) == [(household.id, received.id)]


# The real ledger has no rows before 2000, so real transfers never compete with these.
SYNTHETIC_DAY = date(1999, 1, 1)


@pytest.mark.integration
def test_pair_transfers_labels_both_sides_and_skips_user_labels(db_conn, make_tx):
    def tx(amount, text, iban):
        return make_tx(amount, text, iban=iban, booked_at=SYNTHETIC_DAY)

    out = tx("-4321.09", "TRASPASO | ANA EXAMPLE", "ES0000000000000000000011")
    into = tx("4321.09", "TRASPASO | ANA EXAMPLE", "ES0000000000000000000012")
    mine = tx("-4321.08", "BIZUM ENVIADO", "ES0000000000000000000011")
    tx("4321.08", "BIZUM RECIBIDO", "ES0000000000000000000012")
    db_conn.execute(
        "update transactions set category_source = 'user', category_slug = 'payments_to_people'"
        " where id = %s",
        (mine,),
    )
    db_conn.execute(
        "update transactions set merchant_confidence = 0.9, subscription_score = 0.8 where id = %s",
        (out,),
    )
    pair_transfers(db_conn, Settings())
    rows = db_conn.execute(
        "select id, tx_type, category_slug, category_source, transfer_pair_id,"
        " merchant_confidence, subscription_score from transactions where id = any(%s)",
        ([out, into, mine],),
    ).fetchall()
    by_id = {row["id"]: row for row in rows}
    assert by_id[out]["transfer_pair_id"] == by_id[into]["transfer_pair_id"] is not None
    assert by_id[out]["category_slug"] == "own_accounts" and by_id[out]["tx_type"] == "transfer"
    assert by_id[into]["category_slug"] == "own_accounts" and by_id[into]["tx_type"] == "transfer"
    assert by_id[out]["merchant_confidence"] is None and by_id[out]["subscription_score"] is None
    assert by_id[mine]["transfer_pair_id"] is None and by_id[mine]["category_source"] == "user"
    labels = db_conn.execute(
        "select transaction_id from transaction_labels"
        " where transaction_id = any(%s) and category_slug = 'own_accounts' and source = 'rule'",
        ([out, into, mine],),
    ).fetchall()
    assert sorted(row["transaction_id"] for row in labels) == sorted([out, into])
    # Bound to a name so a failure shows the count, never the Settings repr with its keys.
    paired_again = pair_transfers(db_conn, Settings())
    assert paired_again == 0


@pytest.mark.integration
def test_a_row_the_user_marked_own_accounts_pairs_and_keeps_its_label(db_conn, make_tx):
    mine = make_tx(
        "4321.07",
        "TRASPASO | ANA EXAMPLE",
        iban="ES0000000000000000000011",
        booked_at=SYNTHETIC_DAY,
    )
    other = make_tx(
        "-4321.07",
        "TRANSFERENCIA A ANA EXAMPLE",
        iban="ES0000000000000000000012",
        booked_at=SYNTHETIC_DAY,
    )
    db_conn.execute(
        "update transactions set category_source = 'user', category_slug = 'own_accounts',"
        " tx_type = 'transfer' where id = %s",
        (mine,),
    )
    pair_transfers(db_conn, Settings())
    rows = db_conn.execute(
        "select id, tx_type, category_slug, category_source, transfer_pair_id from transactions"
        " where id = any(%s)",
        ([mine, other],),
    ).fetchall()
    by_id = {row["id"]: row for row in rows}
    assert by_id[mine]["transfer_pair_id"] == by_id[other]["transfer_pair_id"] is not None
    assert by_id[mine]["category_source"] == "user"
    assert by_id[other]["category_source"] == "rule"
    assert by_id[other]["category_slug"] == "own_accounts" and by_id[other]["tx_type"] == "transfer"
    labels = db_conn.execute(
        "select transaction_id from transaction_labels where transaction_id = any(%s)"
        " and source = 'rule'",
        ([mine, other],),
    ).fetchall()
    assert [row["transaction_id"] for row in labels] == [other]
