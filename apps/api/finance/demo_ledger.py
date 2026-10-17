"""Twelve synthetic months for the README screenshots. Temporary: deleted before the PR.

    cd apps/api && uv run python -m finance.demo_ledger \
        postgresql://postgres:postgres@127.0.0.1:54322/scratch_docs

Income stays near 7,540.31 a month and expenses between 3,700 and 4,300. Every name is invented.
"""

import random
import sys
from calendar import monthrange
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from finance.categorization.jev_questions import match_key

CENT = Decimal("0.01")
MONTHS = [(2025, m) for m in (10, 11, 12)] + [(2026, m) for m in range(1, 10)]
EVERYDAY, SAVINGS = "Everyday", "Savings"
ACCOUNTS = {
    EVERYDAY: ("bbva", "ES0000000000000000000101"),
    SAVINGS: ("caixabank", "ES0000000000000000000102"),
}

# Totals per month, to the cent: income is salary plus quarterly interest.
INCOME = {
    (2025, 10): "7540.31", (2025, 11): "7540.31", (2025, 12): "7558.73",
    (2026, 1): "7540.31", (2026, 2): "7540.31", (2026, 3): "7519.19",
    (2026, 4): "7540.31", (2026, 5): "7540.31", (2026, 6): "7560.16",
    (2026, 7): "7588.74", (2026, 8): "7540.31", (2026, 9): "7562.61",
}  # fmt: skip
EXPENSES = {
    (2025, 10): "3842.17", (2025, 11): "3968.40", (2025, 12): "4271.86",
    (2026, 1): "3734.52", (2026, 2): "3811.09", (2026, 3): "3926.63",
    (2026, 4): "4048.27", (2026, 5): "3889.75", (2026, 6): "4112.38",
    (2026, 7): "4196.04", (2026, 8): "4287.91", (2026, 9): "3957.66",
}  # fmt: skip
INTEREST = {3: "21.07", 6: "19.85", 9: "22.30", 12: "18.42"}

# (day, amount, category, merchant, subscription), charged every month
FIXED = [
    (1, "-1350.00", "rent", "Keystone Lettings", False),
    (2, "-54.60", "public_transport", "City Metro", False),
    (3, "-68.40", "health_insurance", "Meridian Health", False),
    (4, "-289.00", "car_costs", "Ridgeway Car Leasing", False),
    (5, "-45.90", "internet_phone", "Fieldline", True),
    (6, "-39.90", "sports_gym", "Pulse Gym", True),
    (8, "-13.99", "entertainment", "Kinora", True),
    (12, "-21.78", "software_ai", "Ledger AI", True),
    (15, "-245.00", "childcare_kids", "Little Oaks Academy", False),
    (20, "-20.00", "donations", "Open Harbor Foundation", False),
]
# (category, merchants, charges a month, min, max)
VARIABLE = [
    ("restaurants_bars", ["Linea Cafe", "Taberna Norte", "Saffron Table"], 8, 16, 82),
    ("fuel", ["Ridge Fuel"], 2, 48, 72),
    ("utilities", ["Bright Current"], 1, 58, 118),
    ("pharmacy", ["Green Cross Pharmacy"], 1, 9, 34),
    ("pets", ["Paws & Co"], 1, 28, 64),
    ("personal_care", ["Studio Nine"], 1, 22, 45),
    ("taxi_rideshare", ["Metro Cabs"], 1, 9, 26),
    ("beauty_perfumery", ["Rosewater Beauty"], 1, 18, 55),
    ("other_shopping", ["Quay Kiosk"], 1, 15, 60),
    ("culture_events", ["Cine Aurora"], 1, 18, 45),
    ("parking_tolls", ["Plaza Parking"], 2, 4, 18),
]
# (year, month, day, amount, category, merchant)
ONE_OFFS = [
    (2025, 10, 18, "-129.95", "fashion", "Atelier North"),
    (2025, 11, 28, "-349.00", "electronics", "Volt Electronics"),
    (2025, 12, 12, "-286.40", "home_goods", "Casa Lumen"),
    (2025, 12, 19, "-214.75", "fashion", "Atelier North"),
    (2025, 12, 22, "-96.00", "culture_events", "Cine Aurora"),
    (2026, 3, 14, "-158.30", "fashion", "Atelier North"),
    (2026, 4, 10, "-212.00", "car_costs", "Ridgeway Car Leasing"),
    (2026, 5, 23, "-74.50", "culture_events", "Cine Aurora"),
    (2026, 6, 6, "-189.99", "home_goods", "Casa Lumen"),
    (2026, 7, 9, "-312.00", "flights", "Skyway Air"),
    (2026, 8, 3, "-486.00", "lodging", "Coastline Stays"),
    (2026, 8, 11, "-94.20", "travel_other", "Coastline Tours"),
    (2026, 9, 12, "-88.60", "books_supplies", "Pylon Books"),
]
GROCERS = ["Mercado Alba", "Verdecampo", "Mercado Alba", "Fresh Corner"]
GROCERY_TICKETS = 12


@dataclass(frozen=True)
class Row:
    account: str
    booked_at: date
    amount: Decimal  # signed: negative is money out
    category: str
    merchant: str | None
    subscription: bool = False


def _month(year: int, month: int, rng: random.Random) -> list[Row]:
    def on(day: int, amount: Decimal, category: str, merchant: str | None, sub=False) -> Row:
        return Row(EVERYDAY, date(year, month, day), amount, category, merchant, sub)

    interest = Decimal(INTEREST.get(month, "0"))
    rows = [on(1, Decimal(INCOME[(year, month)]) - interest, "salary", "Northwind Labs")]
    if interest:
        rows.append(
            Row(SAVINGS, date(year, month, 28), interest, "investment_income", "Harbor Savings")
        )
    rows.append(on(2, Decimal("-2500.00"), "own_accounts", None))
    rows.append(Row(SAVINGS, date(year, month, 2), Decimal("2500.00"), "own_accounts", None))
    rows += [on(d, Decimal(a), c, m, s) for d, a, c, m, s in FIXED]
    for category, merchants, count, low, high in VARIABLE:
        for i in range(count):
            amount = Decimal(str(rng.uniform(low, high))).quantize(CENT)
            rows.append(on(rng.randint(1, 28), -amount, category, merchants[i % len(merchants)]))
    rows += [on(d, Decimal(a), c, m) for y, mo, d, a, c, m in ONE_OFFS if (y, mo) == (year, month)]

    # Groceries take what is left of the month's expense total, split over weekly tickets.
    spent = -sum(r.amount for r in rows if r.amount < 0 and r.category != "own_accounts")
    left = Decimal(EXPENSES[(year, month)]) - spent
    weights = [rng.uniform(0.6, 1.4) for _ in range(GROCERY_TICKETS)]
    parts = [(left * Decimal(str(w / sum(weights)))).quantize(CENT) for w in weights]
    parts[-1] = left - sum(parts[:-1])
    if min(parts) <= 0:
        raise ValueError(f"{year}-{month:02d}: fixed spending exceeds the expense target")
    for i, part in enumerate(parts):
        rows.append(on(min(28, 1 + i * 2 + rng.randint(0, 1)), -part, "groceries", GROCERS[i % 4]))
    return rows


def build_ledger() -> list[Row]:
    rng = random.Random(2026)
    return [row for year, month in MONTHS for row in _month(year, month, rng)]


def require_scratch_docs(db_url: str) -> None:
    """Stop unless the URL opens the database named scratch_docs."""
    if conninfo_to_dict(db_url).get("dbname") != "scratch_docs":
        raise SystemExit(
            "refusing: the synthetic ledger loads only into a database named scratch_docs"
        )


DIRECT_DEBITS = {merchant for _, _, _, merchant, _ in FIXED} | {"Bright Current"}

INSERT_TX = """
insert into transactions (account_id, import_id, booked_at, value_date, amount, description_raw,
    merchant, dedup_key, tx_type, category_slug, category_source, merchant_id, merchant_source,
    is_subscription, needs_review, transfer_pair_id)
values (%(account)s, %(import)s, %(day)s, %(day)s, %(amount)s, %(raw)s, %(text)s, %(key)s,
    %(tx_type)s, %(category)s, 'user', %(merchant)s, %(merchant_source)s, %(sub)s, false, %(pair)s)
"""


def _description(row: Row) -> str:
    if row.category == "own_accounts":
        return "TRASPASO ENTRE CUENTAS PROPIAS"
    if row.amount > 0:
        return f"TRANSFERENCIA RECIBIDA {row.merchant.upper()}"
    if row.merchant in DIRECT_DEBITS:
        return f"RECIBO {row.merchant.upper()}"
    return f"PAGO CON TARJETA {row.merchant.upper()}"


def load(db_url: str) -> None:
    require_scratch_docs(db_url)
    rows = build_ledger()
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        if conn.execute("select count(*) as n from transactions").fetchone()["n"]:
            raise SystemExit("scratch_docs already holds transactions: drop and recreate it")
        tx_types = {
            r["slug"]: r["tx_type"] for r in conn.execute("select slug, tx_type from categories")
        }
        if not tx_types:
            raise SystemExit("no categories: run `finance seed` against scratch_docs first")
        accounts = {
            name: conn.execute(
                "insert into accounts (bank, iban, name) values (%s, %s, %s) returning id",
                (bank, iban, name),
            ).fetchone()["id"]
            for name, (bank, iban) in ACCOUNTS.items()
        }
        merchants: dict[str, object] = {}
        for row in rows:
            if row.merchant and row.merchant not in merchants:
                merchants[row.merchant] = conn.execute(
                    "insert into merchants (name, match_key, confirmed, category_slug,"
                    " is_subscription, cadence) values (%s, %s, true, %s, %s, %s) returning id",
                    (
                        row.merchant,
                        match_key(row.merchant),
                        row.category,
                        row.subscription,
                        "monthly" if row.subscription else None,
                    ),
                ).fetchone()["id"]
        statements = Counter((r.account, r.booked_at.year, r.booked_at.month) for r in rows)
        imports = {}
        for (account, year, month), count in statements.items():
            filename = f"synthetic-{account.lower()}-{year}-{month:02d}.pdf"
            imports[(account, year, month)] = conn.execute(
                "insert into imports (account_id, filename, file_sha256, rows_total, rows_new,"
                " rows_duplicate, period_start, period_end) values (%s, %s, %s, %s, %s, 0, %s, %s)"
                " returning id",
                (
                    accounts[account],
                    filename,
                    sha256(filename.encode()).hexdigest(),
                    count,
                    count,
                    date(year, month, 1),
                    date(year, month, monthrange(year, month)[1]),
                ),
            ).fetchone()["id"]
        pairs: dict[tuple[int, int], object] = {}
        for i, row in enumerate(rows):
            month = (row.booked_at.year, row.booked_at.month)
            conn.execute(INSERT_TX, {
                "account": accounts[row.account],
                "import": imports[(row.account, *month)],
                "day": row.booked_at,
                "amount": row.amount,
                "raw": _description(row),
                "text": row.merchant.upper() if row.merchant else None,
                "key": sha256(f"{i}|{row}".encode()).hexdigest(),
                "tx_type": tx_types[row.category],
                "category": row.category,
                "merchant": merchants.get(row.merchant),
                "merchant_source": "user" if row.merchant else "none",
                "sub": row.subscription,
                "pair": (
                    pairs.setdefault(month, uuid4()) if row.category == "own_accounts" else None
                ),
            })  # fmt: skip
        problems = check(conn)
    if problems:
        raise SystemExit("\n".join(problems))


def check(conn) -> list[str]:
    """Compare v_monthly_summary with the targets; print the months as they stand."""
    got = conn.execute(
        "select month, sum(income) as income, sum(expenses) as expenses"
        " from v_monthly_summary group by month order by month"
    ).fetchall()
    problems = []
    for row in got:
        year, month = (int(part) for part in row["month"].split("-"))
        print(row["month"], row["income"], row["expenses"])
        want = (Decimal(INCOME[(year, month)]), Decimal(EXPENSES[(year, month)]))
        if (row["income"], row["expenses"]) != want:
            problems.append(f"{row['month']}: got {row['income']} / {row['expenses']}, want {want}")
    if len(got) != len(MONTHS):
        problems.append(f"{len(got)} months in v_monthly_summary, want {len(MONTHS)}")
    return problems


if __name__ == "__main__":
    load(sys.argv[1])
