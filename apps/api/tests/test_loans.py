from datetime import date
from decimal import Decimal

import pytest

from finance.categorization.categorizer import from_rule
from finance.categorization.loans import link_loans, loan_merchant_name
from finance.categorization.merchants import MerchantRoster
from finance.categorization.models import TxInput
from finance.categorization.store import save
from finance.categorization.taxonomy import load_taxonomy

CONTRACT = "0000-1111-22-3333334567"  # synthetic contract number
REPAYMENT = "CARGO POR AMORTIZACION DE PRESTAMO/CREDITO"


def test_the_contract_number_names_the_loan():
    assert loan_merchant_name(f"CARGO POR AMORTIZACION DE PRESTAMO/CREDITO | {CONTRACT}") == (
        "Loan ····4567"
    )
    assert loan_merchant_name("CARGO POR AMORTIZACION DE PRESTAMO/CREDITO | ") is None


@pytest.mark.integration
def test_a_disbursement_and_its_instalments_share_one_merchant(db_conn, make_tx):
    rows = [
        make_tx(
            "1500.00",
            f"ABONO POR DISPOSICION DE PRESTAMO/CREDITO | {CONTRACT}",
            booked_at=date(1999, 1, 5),
        ),
        make_tx(
            "-130.00",
            f"CARGO POR AMORTIZACION DE PRESTAMO/CREDITO | {CONTRACT}",
            booked_at=date(1999, 2, 5),
        ),
    ]
    for tx, slug in zip(rows, ["loan_received", "loan_payment"], strict=True):
        db_conn.execute(
            "update transactions set category_slug = %s, category_source = 'rule' where id = %s",
            (slug, tx),
        )
    # the real ledger may hold unlinked loan rows too; the query below checks ours
    assert link_loans(db_conn) >= 2
    found = db_conn.execute(
        "select distinct t.merchant_id, t.merchant_source, m.name from transactions t"
        " join merchants m on m.id = t.merchant_id where t.id = any(%s)",
        (rows,),
    ).fetchall()
    assert [(r["merchant_source"], r["name"]) for r in found] == [("rule", "Loan ····4567")]


@pytest.mark.integration
def test_a_renamed_loan_keeps_its_new_instalments(db_conn, make_tx):
    first = make_tx(
        "-130.00",
        f"CARGO POR AMORTIZACION DE PRESTAMO/CREDITO | {CONTRACT}",
        booked_at=date(1999, 2, 5),
    )
    db_conn.execute(
        "update transactions set category_slug = 'loan_payment' where id = %s", (first,)
    )
    link_loans(db_conn)
    db_conn.execute(
        "update merchants set name = 'ZZTEST car loan', match_key = 'ZZTESTCARLOAN'"
        " where id = (select merchant_id from transactions where id = %s)",
        (first,),
    )
    later = make_tx(
        "-130.00",
        f"CARGO POR AMORTIZACION DE PRESTAMO/CREDITO | {CONTRACT}",
        booked_at=date(1999, 3, 5),
    )
    db_conn.execute(
        "update transactions set category_slug = 'loan_payment' where id = %s", (later,)
    )
    link_loans(db_conn)
    names = db_conn.execute(
        "select distinct m.name from transactions t join merchants m on m.id = t.merchant_id"
        " where t.id = any(%s)",
        ([first, later],),
    ).fetchall()
    assert [r["name"] for r in names] == ["ZZTEST car loan"]


@pytest.mark.integration
def test_a_renamed_loan_survives_a_full_re_categorization(db_conn, make_tx):
    text = f"{REPAYMENT} | {CONTRACT}"
    tx = make_tx("-130.00", text, bank_concept=REPAYMENT, booked_at=date(1999, 2, 5))
    db_conn.execute(
        "update transactions set category_slug = 'loan_payment', category_source = 'rule'"
        " where id = %s",
        (tx,),
    )
    link_loans(db_conn)
    db_conn.execute(
        "update merchants set name = 'ZZTEST car loan', match_key = 'ZZTESTCARLOAN'"
        " where id = (select merchant_id from transactions where id = %s)",
        (tx,),
    )
    # What an --all run saves for this row: the loan rule's result, which names no merchant.
    # Built from the synthetic row only; categorize_pending(include_all=True) would touch real rows.
    row = TxInput(
        id=tx,
        bank="bbva",
        booked_at=date(1999, 2, 5),
        amount=Decimal("-130.00"),
        description_raw=text,
        bank_concept=REPAYMENT,
    )
    save(db_conn, [from_rule(row, "loan_payment", load_taxonomy(db_conn))], MerchantRoster([]))
    found = db_conn.execute(
        "select t.merchant_source, m.name from transactions t"
        " left join merchants m on m.id = t.merchant_id where t.id = %s",
        (tx,),
    ).fetchone()
    assert (found["merchant_source"], found["name"]) == ("rule", "ZZTEST car loan")
