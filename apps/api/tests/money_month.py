"""One synthetic month (January 1999) and one row in February that exercise every money rule
in spec section 2. Totals, worked by hand:
  income   = 2000 (salary)
  expenses = (200 - 80) fashion + 130 loan + 175 card + (80 - 60) restaurants + 10 uncategorized
           = 455
  savings  = 1545;  February: fashion refund of 30 with no purchase = expenses -30.
Transfers (loan received, own accounts) are out of every total."""

from datetime import date
from uuid import UUID, uuid4

IBAN = "ES0000000000000000000077"

ROWS = [  # (amount, category or None, day, description)
    ("2000.00", "salary", date(1999, 1, 28), "ZZTEST PAYROLL"),
    ("-200.00", "fashion", date(1999, 1, 3), "ZZTEST SHOP"),
    ("80.00", "fashion", date(1999, 1, 10), "ZZTEST SHOP REFUND"),
    ("1500.00", "loan_received", date(1999, 1, 5), "ZZTEST LOAN IN"),
    ("-130.00", "loan_payment", date(1999, 1, 20), "ZZTEST LOAN OUT"),
    ("-175.00", "credit_card_spending", date(1999, 1, 2), "ZZTEST CARD"),
    ("-300.00", "own_accounts", date(1999, 1, 15), "ZZTEST TO SAVINGS"),
    ("50.00", "own_accounts", date(1999, 1, 16), "ZZTEST FROM OLD ACCOUNT"),
    ("-80.00", "restaurants_bars", date(1999, 1, 12), "ZZTEST DINNER"),
    ("60.00", "restaurants_bars", date(1999, 1, 13), "ZZTEST BIZUM BACK"),
    ("-10.00", None, date(1999, 1, 30), "ZZTEST UNKNOWN"),
    ("30.00", "fashion", date(1999, 2, 2), "ZZTEST LATE REFUND"),
]


def money_month(db_conn, make_tx) -> UUID:
    ids = []
    for amount, slug, day, text in ROWS:
        tx = make_tx(amount, text, iban=IBAN, booked_at=day)
        if slug:
            db_conn.execute(
                "update transactions t set category_slug = c.slug, tx_type = c.tx_type,"
                " category_source = 'user' from categories c where c.slug = %s and t.id = %s",
                (slug, tx),
            )
        ids.append(tx)
    db_conn.execute(  # the move to savings pairs with an imported account
        "update transactions set transfer_pair_id = %s where id = %s", (uuid4(), ids[6])
    )
    return db_conn.execute("select id from accounts where iban = %s", (IBAN,)).fetchone()["id"]
