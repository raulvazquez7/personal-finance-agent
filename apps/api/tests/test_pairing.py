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


def test_card_purchases_never_pair():
    out, into = _tx(A, "-20", "PAGO CON TARJETA | ACME"), _tx(B, "20", "DEVOLUCION ACME")
    assert find_pairs([out, into], PATTERN, 2) == []


def test_pairing_is_one_to_one_and_prefers_the_nearest_date():
    out = _tx(A, "-50", "BIZUM ENVIADO", day=3)
    far, near = _tx(B, "50", "BIZUM RECIBIDO", day=1), _tx(C, "50", "BIZUM RECIBIDO", day=3)
    second_out = _tx(A, "-50", "BIZUM ENVIADO", day=4)
    pairs = find_pairs([out, far, near, second_out], PATTERN, 2)
    assert pairs == [(out.id, near.id)]


@pytest.mark.integration
def test_pair_transfers_labels_both_sides_and_skips_user_labels(db_conn, make_tx):
    out = make_tx("-4321.09", "TRASPASO | ANA EXAMPLE", iban="ES0000000000000000000011")
    into = make_tx("4321.09", "TRASPASO | ANA EXAMPLE", iban="ES0000000000000000000012")
    mine = make_tx("-4321.08", "BIZUM ENVIADO", iban="ES0000000000000000000011")
    make_tx("4321.08", "BIZUM RECIBIDO", iban="ES0000000000000000000012")
    db_conn.execute(
        "update transactions set category_source = 'user', category_slug = 'payments_to_people'"
        " where id = %s",
        (mine,),
    )
    pair_transfers(db_conn, Settings())
    rows = db_conn.execute(
        "select id, tx_type, category_slug, category_source, transfer_pair_id from transactions"
        " where id = any(%s)",
        ([out, into, mine],),
    ).fetchall()
    by_id = {row["id"]: row for row in rows}
    assert by_id[out]["transfer_pair_id"] == by_id[into]["transfer_pair_id"] is not None
    assert by_id[out]["category_slug"] == "own_accounts" and by_id[out]["tx_type"] == "transfer"
    assert by_id[into]["category_slug"] == "own_accounts" and by_id[into]["tx_type"] == "transfer"
    assert by_id[mine]["transfer_pair_id"] is None and by_id[mine]["category_source"] == "user"
    labels = db_conn.execute(
        "select transaction_id from transaction_labels"
        " where transaction_id = any(%s) and category_slug = 'own_accounts' and source = 'rule'",
        ([out, into, mine],),
    ).fetchall()
    assert sorted(row["transaction_id"] for row in labels) == sorted([out, into])
