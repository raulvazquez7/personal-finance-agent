# Public face Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the README with a short product page, add `docs/architecture.md` for reviewers, and capture three real screenshots of tally ai running on twelve months of synthetic data. Delete the data machinery before the PR.

**Architecture:** A temporary, pure generator (`build_ledger`) produces the synthetic ledger, and a guarded loader writes it into a scratch database called `scratch_docs`. The real API and a production build of the web serve that database on :8001/:3001, where agent-browser reads the values back and captures the pages. The docs are written from the code and from `docs/evals/HISTORY.md`. The last task deletes the generator, its test and the database.

**Tech Stack:** Python 3.12, psycopg 3, pytest, the local Supabase Postgres cluster (:54322), FastAPI, Next.js 16 (production build), agent-browser 0.38, Markdown and Mermaid.

**Spec:** `docs/superpowers/specs/2026-10-17-public-face-design.md`

## Global Constraints

- English everywhere: docs, alt text, code, commits.
- No figure, merchant, IBAN or statement from `data/raw/`, `data/labels/` or the real database
  enters code, screenshots or docs. Do not open `data/`.
- Every command that touches a database exports
  `SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/scratch_docs`. The repo `.env`
  points at the real database. Never edit `.env`, never print a secret, never run
  `supabase db reset`, never `pg_dump` the real database.
- The loader refuses any database whose name is not exactly `scratch_docs`.
- Browse only `http://localhost:3001`. agent-browser session `public-face`, absolute paths for
  `screenshot`, `close` at the end. Load `agent-browser skills get core` before the first command.
- `cd apps/api && uv run task test` and `uv run task lint` pass at the end of every task that
  touches Python.
- Conventional commits. Do not push until Raul asks. Push command is in `CLAUDE.md`.
- Eval figures, verbatim: 684 golden rows, level-2 accuracy 87.0%, precision 98.2% at 0.95,
  397 accepted, 287 to review (2026-09-27). Spike: 99% on the 254 rows scored ≥ 0.95. Never
  print "99%" without the 254-row sentence.
- The words "jev router" appear only in the sentence that says the router was not built.

## Before Task 1 (controller, not a subagent)

Raul's parallel PR (imports coverage and the settings taxonomy) merges first.

1. Bring the branch up to date: from the worktree, `git fetch origin && git merge origin/main`.
2. Run `git diff 09c7e13..origin/main --stat` (`09c7e13` is the `main` these specs were
   checked against) and check whether the merge touched `apps/web/src/app/page.tsx`,
   `apps/web/src/app/spending/`, `apps/web/src/app/chat/`, `apps/api/finance/agent/`,
   `apps/api/finance/categorization/`, `supabase/migrations/` or `docs/evals/HISTORY.md`. If it
   touched any of them, re-check spec section 3 against the new code. Amend the spec and this
   plan in a `docs:` commit before Task 1.
3. Check that the local cluster is up (`supabase status`) and that Raul's `XAI_API_KEY` is set in
   the main checkout's `.env`. Check by name only, without printing the value:
   `grep -c '^XAI_API_KEY=.\+' "<main checkout>/.env"` returns `1`.
4. If `git status` in the main checkout still lists the untracked drafts
   `docs/superpowers/specs/2026-10-16-public-docs-design.md` and
   `docs/superpowers/plans/2026-10-16-public-docs.md`, remind Raul that this spec supersedes them.
   They are his files, so do not delete them.

## Review Focus

- **A month whose fixed charges exceed its target.** Expected: generation fails loudly, never
  a negative grocery ticket. The test asserts every ticket is positive.
- **The loader pointed at the real database.** Expected: it refuses before connecting. The test
  covers `postgres`, `scratch_review`, a URL with no dbname, and a key=value conninfo.
- **Running the loader twice on `scratch_docs`.** Expected: it refuses because transactions
  already exist, rather than doubling every total. Step 4 of Task 2 runs it twice on purpose.
- **A chat answer with an amount that no query returned (backlog 8).** Expected: the capture is
  rejected. Task 3 compares every amount in the answer against the query rows and `psql`.
- **A screenshot with an IBAN, a real merchant or an unrendered chart.** Expected: rejected. Task 3
  reads each PNG. Task 5 greps for IBANs and counts name collisions with the real database.

---

## File structure

| Path | Responsibility | After the PR |
|---|---|---|
| `apps/api/finance/demo_ledger.py` | Synthetic ledger (pure) plus the guarded loader and check | deleted in Task 5 |
| `apps/api/tests/test_demo_ledger.py` | Totals, shape and guard of the ledger, with no database | deleted in Task 5 |
| `docs/images/overview.png`, `docs/images/spending-shopping.png`, `docs/images/chat.png` | Captures | kept |
| `README.md` | Product page | replaced |
| `docs/architecture.md` | Reviewer page | new |

---

### Task 1: The synthetic ledger (pure)

**Files:**
- Create: `apps/api/finance/demo_ledger.py`
- Test: `apps/api/tests/test_demo_ledger.py`

**Interfaces:**
- Produces: `Row` (frozen dataclass: `account: str`, `booked_at: date`, `amount: Decimal`, `category: str`,
  `merchant: str | None`, `subscription: bool`); `build_ledger() -> list[Row]`;
  `MONTHS: list[tuple[int, int]]`; `INCOME`, `EXPENSES: dict[tuple[int, int], str]`;
  `ACCOUNTS: dict[str, tuple[str, str]]` (name to `(bank, iban)`);
  `require_scratch_docs(db_url: str) -> None`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_demo_ledger.py`:

```python
"""The synthetic ledger behind the README screenshots. Deleted with the generator."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

import pytest

from finance.demo_ledger import (
    ACCOUNTS,
    EXPENSES,
    INCOME,
    MONTHS,
    build_ledger,
    require_scratch_docs,
)

INCOME_CATEGORIES = {"salary", "investment_income"}
TRANSFER = "own_accounts"


def _by_month(rows, keep):
    totals = defaultdict(Decimal)
    for row in rows:
        if keep(row):
            totals[(row.booked_at.year, row.booked_at.month)] += row.amount
    return totals


def test_every_month_lands_on_its_income_and_expense_totals():
    rows = build_ledger()
    income = _by_month(rows, lambda r: r.category in INCOME_CATEGORIES)
    expenses = _by_month(rows, lambda r: r.category not in INCOME_CATEGORIES | {TRANSFER})
    assert {m: str(v) for m, v in income.items()} == INCOME
    assert {m: str(-v) for m, v in expenses.items()} == EXPENSES


def test_twelve_full_months_ending_in_september_2026():
    rows = build_ledger()
    assert MONTHS[0] == (2025, 10) and MONTHS[-1] == (2026, 9) and len(MONTHS) == 12
    assert {(r.booked_at.year, r.booked_at.month) for r in rows} == set(MONTHS)
    assert max(r.booked_at for r in rows) <= date(2026, 9, 30)


def test_salary_is_the_same_in_ten_months():
    salaries = [r.amount for r in build_ledger() if r.category == "salary"]
    assert len(salaries) == 12
    assert salaries.count(Decimal("7540.31")) == 10


def test_groceries_stay_realistic_and_every_ticket_is_positive():
    rows = build_ledger()
    groceries = _by_month(rows, lambda r: r.category == "groceries")
    assert all(Decimal("550") <= -v <= Decimal("1100") for v in groceries.values())
    assert all(r.amount < 0 for r in rows if r.category == "groceries")


def test_amounts_are_cents_and_spending_is_money_out():
    rows = build_ledger()
    assert all(r.amount == r.amount.quantize(Decimal("0.01")) for r in rows)
    assert all(r.amount != 0 for r in rows)
    spending = [r for r in rows if r.category not in INCOME_CATEGORIES | {TRANSFER}]
    assert all(r.amount < 0 for r in spending)


def test_each_month_moves_savings_as_one_pair_that_nets_to_zero():
    rows = build_ledger()
    for month in MONTHS:
        pair = [
            r
            for r in rows
            if r.category == TRANSFER and (r.booked_at.year, r.booked_at.month) == month
        ]
        assert len(pair) == 2 and sum(r.amount for r in pair) == 0
        assert {r.account for r in pair} == set(ACCOUNTS)


def test_every_merchant_has_one_category_and_subscriptions_are_monthly_charges():
    rows = build_ledger()
    categories = defaultdict(set)
    for row in rows:
        if row.merchant:
            categories[row.merchant].add(row.category)
    assert all(len(slugs) == 1 for slugs in categories.values())
    subscriptions = {r.merchant for r in rows if r.subscription}
    assert len(subscriptions) == 4
    for merchant in subscriptions:
        assert sum(1 for r in rows if r.merchant == merchant) == 12


def test_only_fake_ibans_and_the_build_is_deterministic():
    assert all(iban.startswith("ES00") and len(iban) == 24 for _, iban in ACCOUNTS.values())
    assert build_ledger() == build_ledger()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
        "postgresql://postgres:postgres@127.0.0.1:54322/scratch_review",
        "postgresql://postgres:postgres@127.0.0.1:54322",
        "host=127.0.0.1 port=54322 dbname=postgres user=postgres",
    ],
)
def test_the_loader_refuses_any_database_but_scratch_docs(url):
    with pytest.raises(SystemExit):
        require_scratch_docs(url)


def test_the_loader_accepts_scratch_docs():
    require_scratch_docs("postgresql://postgres:postgres@127.0.0.1:54322/scratch_docs")
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd apps/api && uv run pytest tests/test_demo_ledger.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'finance.demo_ledger'`.

- [ ] **Step 3: Write the generator**

Create `apps/api/finance/demo_ledger.py`. The merchant names are invented. Do not swap in real
brands.

```python
"""Twelve synthetic months for the README screenshots. Temporary: deleted before the PR.

    cd apps/api && uv run python -m finance.demo_ledger \
        postgresql://postgres:postgres@127.0.0.1:54322/scratch_docs

Income stays near 7,540.31 a month and expenses between 3,700 and 4,300. Every name is invented.
"""

import random
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from psycopg.conninfo import conninfo_to_dict

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
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `cd apps/api && uv run pytest tests/test_demo_ledger.py -v`
Expected: all tests pass. If the grocery range test fails, report it. Do not widen the range:
a failure means the spec's targets and the fixed charges disagree.

- [ ] **Step 5: Lint and full unit suite**

Run: `cd apps/api && uv run task lint && uv run task test`
Expected: both pass. If `ruff format --check` reflows the `INCOME`/`EXPENSES` tables, keep the
`# fmt: skip` markers and apply only the formatter's other changes.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/demo_ledger.py apps/api/tests/test_demo_ledger.py
git commit -m "chore: synthetic twelve-month ledger for the README screenshots (temporary)"
```

---

### Task 2: Load it into `scratch_docs`

**Files:**
- Modify: `apps/api/finance/demo_ledger.py` (append the loader, the check and `__main__`)

**Interfaces:**
- Consumes: `build_ledger`, `ACCOUNTS`, `INCOME`, `EXPENSES`, `FIXED`, `require_scratch_docs` from Task 1;
  `finance.categorization.jev_questions.match_key(name: str) -> str`.
- Produces: `load(db_url: str) -> None`; `check(conn) -> list[str]` (mismatch messages, empty when every
  month matches); a running `scratch_docs` with the ledger, used by Task 3.

- [ ] **Step 1: Append the loader**

Add these imports at the top of `apps/api/finance/demo_ledger.py`, keeping isort order:

```python
import sys
from calendar import monthrange
from collections import Counter
from hashlib import sha256
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from finance.categorization.jev_questions import match_key
```

Append this to the end of the file:

```python
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
        tx_types = {r["slug"]: r["tx_type"] for r in conn.execute("select slug, tx_type from categories")}
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
                    (row.merchant, match_key(row.merchant), row.category, row.subscription,
                     "monthly" if row.subscription else None),
                ).fetchone()["id"]
        statements = Counter((r.account, r.booked_at.year, r.booked_at.month) for r in rows)
        imports = {}
        for (account, year, month), count in statements.items():
            filename = f"synthetic-{account.lower()}-{year}-{month:02d}.pdf"
            imports[(account, year, month)] = conn.execute(
                "insert into imports (account_id, filename, file_sha256, rows_total, rows_new,"
                " rows_duplicate, period_start, period_end) values (%s, %s, %s, %s, %s, 0, %s, %s)"
                " returning id",
                (accounts[account], filename, sha256(filename.encode()).hexdigest(), count, count,
                 date(year, month, 1), date(year, month, monthrange(year, month)[1])),
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
                "pair": pairs.setdefault(month, uuid4()) if row.category == "own_accounts" else None,
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
```

- [ ] **Step 2: Lint and unit tests**

Run: `cd apps/api && uv run task lint && uv run task test`
Expected: both pass. The Task 1 tests still pass, and the loader has no unit test of its own:
it is exercised against the database in the next steps.

- [ ] **Step 3: Create `scratch_docs` from the migrations**

The local cluster must be up (`supabase status`). From the worktree root:

```bash
export PGHOST=127.0.0.1 PGPORT=54322 PGUSER=postgres PGPASSWORD=postgres
dropdb --if-exists scratch_docs && createdb scratch_docs
for f in supabase/migrations/*.sql; do psql -v ON_ERROR_STOP=1 -q -d scratch_docs -f "$f" || break; done
cd apps/api && SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/scratch_docs uv run finance seed
```

Expected: no psql error, and `finance seed` reports the categories and rules. If the Homebrew
`psql` is too old for the server, run the same loop through
`docker exec -i supabase_db_personal-finance-agent psql -U postgres -d scratch_docs < "$f"`.
Check the role: `psql -d scratch_docs -tAc "select has_table_privilege('agent_reader','agent.transactions','select')"`
prints `t`.

- [ ] **Step 4: Load, then try loading again**

```bash
cd apps/api && uv run python -m finance.demo_ledger postgresql://postgres:postgres@127.0.0.1:54322/scratch_docs
cd apps/api && uv run python -m finance.demo_ledger postgresql://postgres:postgres@127.0.0.1:54322/scratch_docs
cd apps/api && uv run python -m finance.demo_ledger postgresql://postgres:postgres@127.0.0.1:54322/postgres
```

Expected:
- The first run prints twelve lines from `2025-10 7540.31 3842.17` to `2026-09 7562.61 3957.66`
  and exits 0.
- The second run exits non-zero with "already holds transactions".
- The third run exits non-zero with "refusing" and never connects.

- [ ] **Step 5: Spot-check what the pages will read**

```bash
psql -d scratch_docs -tAc "select count(*) from transactions where category_source <> 'user' or needs_review"
psql -d scratch_docs -tAc "select merchant_name, cadence, active from v_subscriptions order by merchant_name"
psql -d scratch_docs -tAc "select category_slug, sum(spend) from v_transactions_enriched where month = '2026-09' and level1 = 'shopping' group by 1 order by 2 desc"
```

Expected:
- The first query prints `0`.
- The second lists Fieldline, Kinora, Ledger AI and Pulse Gym, all `monthly`, all active.
- The third lists groceries first.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/demo_ledger.py
git commit -m "chore: load the synthetic ledger into scratch_docs only (temporary)"
```

---

### Task 3: The three screenshots

**Files:**
- Create: `docs/images/overview.png`, `docs/images/spending-shopping.png`, `docs/images/chat.png`

**Interfaces:**
- Consumes: `scratch_docs` loaded by Task 2.
- Produces: the three PNGs that Task 4's README and `docs/architecture.md` reference by these exact paths.

- [ ] **Step 1: Start the real API on :8001 against `scratch_docs`**

The worktree has no `.env`. In one shell, export only the xAI key from the main checkout's
`.env` without echoing it, switch everything else off, and start the API:

```bash
cd apps/api && uv sync --group dev
set -a; source <(grep '^XAI_API_KEY=' "<main checkout>/.env"); set +a; \
  cd apps/api && SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/scratch_docs \
  CORS_ORIGINS='["http://localhost:3001"]' TYPESAFE_API_KEY= LANGFUSE_TRACING_ENABLED=false \
  LANGFUSE_PUBLIC_KEY= LANGFUSE_SECRET_KEY= \
  uv run uvicorn finance.api.main:app --port 8001
```

Leave it running (background). Expected: startup completes. The chat opens, the semantic-layer
check passes, and `curl -s localhost:8001/chat/threads` returns `[]` rather than a 503.

- [ ] **Step 2: Start the web as a production build on :3001**

```bash
cd apps/web && npm install
cd apps/web && NEXT_PUBLIC_API_URL=http://localhost:8001 npx next build && NEXT_PUBLIC_API_URL=http://localhost:8001 npx next start -p 3001
```

Leave it running (background). Expected: `curl -s -o /dev/null -w '%{http_code}' localhost:3001/` prints `200`.

- [ ] **Step 3: Overview**

Run `agent-browser skills get core` first. Then:

```bash
agent-browser --session public-face viewport 1440 900
agent-browser --session public-face media light
agent-browser --session public-face open http://localhost:3001/
agent-browser --session public-face wait --text "Last 12 months"
agent-browser --session public-face snapshot
```

Read the snapshot. It must show:
- the September 2026 period;
- income 7,562.61 and expenses 3,957.66, in the UI's currency format;
- a savings tile;
- the "Last 12 months" card with no "no data" month.

If the 12-month card sits below the first 900 px, raise the viewport height in 100 px steps,
up to 1400, until it is fully visible. Record the height used. Then capture it:

```bash
agent-browser --session public-face screenshot "<worktree>/docs/images/overview.png"
```

Open the PNG with the Read tool. The charts must be rendered and contain no IBAN. If they are
not, re-capture.

- [ ] **Step 4: Shopping**

```bash
agent-browser --session public-face open http://localhost:3001/spending/shopping
agent-browser --session public-face wait --text "Groceries"
agent-browser --session public-face snapshot
```

The snapshot shows the September 2026 shopping total, groceries as the largest category, and
Mercado Alba, Verdecampo and Fresh Corner among the top merchants. Use the same viewport rule
as Step 3. Capture it to `<worktree>/docs/images/spending-shopping.png`, then read the PNG back.

- [ ] **Step 5: Chat, one real turn**

```bash
agent-browser --session public-face open http://localhost:3001/chat
agent-browser --session public-face snapshot -i
```

Fill the message box with exactly
`How much did I spend on restaurants each month this year, and which month was highest?`
and press Enter. Wait until the answer finishes (the feedback buttons appear), then snapshot.
Get the thread id from the URL (`/chat/<id>`).

Check the answer before capturing:

```bash
curl -s localhost:8001/chat/threads/<id>/messages > "$TMPDIR/chat.json"
psql -d scratch_docs -tAc "select month, sum(spend) from v_transactions_enriched where category_slug = 'restaurants_bars' and booked_at >= '2026-01-01' group by 1 order by 1"
```

Every amount in the assistant `content` must appear in the rows of one of that message's
`queries`, and those rows must equal the psql output, month by month. The month named as the
highest must be the psql maximum. If any of this fails, delete the thread from the UI and ask
again, up to three turns in total. If all three fail, stop and follow Step 6.

When the answer passes, click the "Ran N queries" disclosure so the SQL and rows are visible,
snapshot to confirm, and capture `<worktree>/docs/images/chat.png`. Read the PNG back.

- [ ] **Step 6: Fallback, only if Step 5 failed three times**

Stop the API from Step 1. Tell Raul the real turn failed three times and include the mismatches.
Then implement the stored thread in spec section 6.3, add it to the loader in a separate
`chore:` commit, serve it with
`CORS_ORIGINS='["http://localhost:3001"]' uv run python -m tests.scripted_chat_server --port 8001 --db-url postgresql://postgres:postgres@127.0.0.1:54322/scratch_docs`,
and capture `/chat/<id>`. The caption in Task 4 then reads "Replayed from a stored answer on
the synthetic data".

- [ ] **Step 7: Close the browser and check the console**

```bash
agent-browser --session public-face errors
agent-browser --session public-face close
```

Expected: `errors` is empty. Leave the API and web running if Task 4 needs a re-capture, and
stop them otherwise.

- [ ] **Step 8: Commit**

```bash
git add docs/images/overview.png docs/images/spending-shopping.png docs/images/chat.png
git commit -m "docs: screenshots of tally ai on synthetic data"
```

---

### Task 4: README and architecture page

**Files:**
- Replace: `README.md`
- Create: `docs/architecture.md`

**Interfaces:**
- Consumes: the three PNG paths from Task 3, and the chat question and answer used there.
- Produces: the anchors `#pipeline`, `#categorization`, `#evals`, `#chat`, `#money`, `#privacy`,
  `#where-to-read-next` and `#limits` in `docs/architecture.md`. The README links four of them.

- [ ] **Step 1: Write `README.md`**

Replace the whole file with the text below.

````markdown
# tally ai

Local-first personal finance. Import your bank's PDF statements, let a rules → jev → human
cascade categorize every movement, see where each month went, and ask questions in plain
language.

![tally ai overview for September 2026 with synthetic data: income, expenses, savings and the last 12 months](docs/images/overview.png)

<sub>Every screenshot shows twelve months of synthetic data.</sub>

## What it does

- **Imports without duplicates.** Upload a BBVA or CaixaBank PDF statement. Uploading it again
  adds nothing.
- **Learns each merchant once.** Rules and jev categorize. What jev is unsure about waits in a
  review inbox, one decision per merchant.
- **Shows the month.** Income, spending, savings rate, a 12-month trend, every category and
  merchant, and the subscriptions you pay.
- **Answers questions.** A chat agent queries your data with read-only SQL and shows the query
  behind every answer.

![Shopping in September 2026: 12-month bars by category, the category treemap and top merchants](docs/images/spending-shopping.png)

![A chat answer with its SQL query opened beside it](docs/images/chat.png)

## How it is built

```mermaid
flowchart LR
    A[PDF statement] --> B[Parse and deduplicate]
    B --> C{Own transfer or<br/>system rule?}
    C -->|yes| G[(Postgres)]
    C -->|no| D["jev: merchant, category,<br/>subscription in one call"]
    D --> E{"Python: merchant match,<br/>confidence ≥ 0.95?"}
    E -->|yes| G
    E -->|no| F[Review inbox] --> G
    G --> H[One enriched view]
    H --> I[Dashboards]
    H --> J["Chat agent<br/>(read-only SQL)"]
```

- **jev chooses, Python decides.** [jev](https://typesafe.ai) answers three typed questions
  per transaction: which fragment of the bank text is the merchant, which category it is, and
  whether it is a subscription. Each comes back with a probability per option. Deterministic
  code does everything else: parsing, deduplication, transfer pairing, merchant matching and
  thresholds. [Categorization →](docs/architecture.md#categorization)
- **Measured, not assumed.** On the latest eval (684 hand-labelled transactions), 87.0% get
  the right category. At the 0.95 threshold the cascade accepts 397 of them with 98.2%
  precision and sends 287 to review. The threshold comes from the spike, where jev was right
  on 99% of the 254 rows it scored at 0.95 or more. [Evals →](docs/architecture.md#evals)
- **A ReAct agent over a semantic layer.** LangChain `create_agent` with one tool, `run_sql`,
  and a LangGraph Postgres checkpointer for each chat's memory. The agent queries two views
  through a read-only Postgres role, with an xAI grok model by default. [Chat →](docs/architecture.md#chat)
- **One money contract.** Every total, on every page and in the chat, comes from one view under
  written rules for refunds, card settlements, transfers and loans. [Money →](docs/architecture.md#money)

**Stack:** Python 3.12, FastAPI, Supabase Postgres, LangChain and LangGraph, jev (TypeSafe AI),
xAI grok, Langfuse, Next.js 16, the AI SDK and shadcn/ui.

## Run it locally

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node 22 and the
[Supabase CLI](https://supabase.com/docs/guides/cli).

```bash
cp .env.example .env     # SUPABASE_DB_URL is required; TYPESAFE_API_KEY categorizes; XAI_API_KEY enables the chat
supabase start           # local Postgres; put its DB URL in .env as SUPABASE_DB_URL
supabase db reset        # first run only: applies the migrations to an empty database
(cd apps/api && uv sync --group dev && uv run finance seed)
```

```bash
cd apps/api && uv run task api     # terminal 1: API on :8000
cd apps/web && npm install && npm run dev   # terminal 2: web on :3000
```

Open http://localhost:3000/imports and upload a statement. With `TYPESAFE_API_KEY` set, it is
categorized right away, and http://localhost:3000/review holds what jev was unsure about.

`supabase db reset` deletes your labels and merchant defaults. Once you have labels, run
`uv run finance labels export` first, and apply new migrations with `supabase migration up`
instead. The commands and the restore procedure are in [CLAUDE.md](CLAUDE.md).

## Limits

- Reads BBVA and CaixaBank PDF statements only.
- The chat is told to answer only with figures it queried, but nothing enforces that yet, and
  there are no chat evals.
- Single-user and local: the tables have no row-level security, so do not host it as is.

More in [docs/architecture.md](docs/architecture.md#limits).

## License

MIT, see [LICENSE](LICENSE).
````

If Task 3 used the fallback, add the caption
`<sub>The chat answer is replayed from stored data.</sub>` under the chat image.

- [ ] **Step 2: Write `docs/architecture.md`**

Create the file with the text below. Each technical claim was checked against the code on
2026-10-17. Step 3 has a reviewer re-check them.

````markdown
# How tally ai is built

This page is for someone checking the code. It explains what each part does and why, and links
to the source of every claim. It is not the spec, the prompt or the API reference: those are
linked at the end.

## Pipeline

```mermaid
flowchart TD
    A[PDF statement] --> B["Parse, normalize, deduplicate<br/>(card number removed from the text)"]
    B --> C[Pair transfers between own accounts]
    C --> D{System rule?<br/>ATM, Bizum, card settlement, loan, paired transfer}
    D -->|yes| H[(Saved)]
    D -->|no| E["jev System One: one call,<br/>three typed questions"]
    E --> F["Python: exact merchant match, merge at ≥ 0.8,<br/>merchant default wins, level 1 from level 2"]
    F -->|confidence ≥ 0.95| H
    F -->|below| G["/review inbox, once per merchant"] --> H
    H --> L[link_loans]
    L --> V[v_transactions_enriched]
    V --> W[Dashboards]
    V --> X["agent.transactions, agent.subscriptions"] --> Y[Chat agent]
```

Ingestion reads BBVA and CaixaBank PDFs (`apps/api/finance/ingestion/`). A movement's dedup key
hashes the account, date, amount, description, printed balance and occurrence, so uploading the
same file twice adds nothing.

## Categorization

Bank lines are cryptic (`PAGO CON TARJETA EN SUPERMERCADOS | … SUPER ACME 0042 L`), and a person
wants "Super Acme, Shopping > Groceries". [jev](https://typesafe.ai), TypeSafe AI's System One
model, makes the judgment calls. It does not generate text. It answers typed questions about a
JSON state: a [`Choice`](https://docs.typesafe.ai/primitives/choice) returns a probability for
every option, and a [`Noul`](https://docs.typesafe.ai/primitives/noul) returns the probability
of yes.

- **Code proposes, jev chooses.** Python cuts the text into 1–4 word fragments, and jev picks the
  brand name
  ([pre-parsed value extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook)).
  There is no merchant list to maintain.
- **One call, three questions.** The merchant fragment, the level-2 category and the
  subscription question are asked together and answered independently
  ([parallel questions](https://docs.typesafe.ai/cookbooks/parallel_questions);
  `apps/api/finance/categorization/jev_questions.py`).
- **Two levels from one question.** Level 1 and its confidence come from summing the leaf
  probabilities
  ([classification using confidence](https://docs.typesafe.ai/cookbooks/classification_using_confidence)).
- **Confidence drives routing.** Rows under 0.95 go to a person. The same merchant is merged
  only at ≥ 0.8 (`merge_threshold` in `apps/api/finance/settings.py`). A merchant the user has
  labelled keeps that label as its default.
- **Where 0.95 came from.** In the [jev spike](superpowers/spikes/2026-09-23-jev-categorization/README.md)
  (412 hand-checked rows), jev was right on 99% of the 254 rows it scored at 0.95 or more.
  Below that, a higher score was not more reliable: a 0.88 was about as often right as a 0.75.

Deterministic Python owns everything that is not a judgment call: parsing, deduplication,
transfer pairing, system rules, merchant matching, thresholds and `link_loans`, which links
loan instalments to their loan after save.

## Evals

`finance eval-categorization --note "…"` runs the production cascade as a dry run against the
golden set (the user's labels). It appends one line to [`HISTORY.md`](evals/HISTORY.md) and
records the run's jev calls as one Langfuse trace. Row-level results stay in the git-ignored
`eval-output/`.

The latest line (2026-09-27, 684 golden rows): level-2 accuracy 87.0%, level-1 accuracy 89.2%.
At the 0.95 threshold, 397 rows are accepted with 98.2% precision and 287 go to review.
Subscription precision is 50/51 and recall 50/60.

Read the history with two caveats. The golden set grew between lines (412, then 480, then 684
rows), so the lines are not a trend. And run-to-run noise is about ten rows, so smaller
differences mean nothing.

## Chat

The chat does not use jev. It is an LLM (`xai:grok-4.7` by default) over a semantic layer.

- **One agent, one tool.** A ReAct loop built with LangChain's
  [`create_agent`](https://docs.langchain.com/oss/python/langchain/agents)
  (`apps/api/finance/agent/graph.py`) and a single tool, `run_sql`, that runs one read-only
  `SELECT`. There is no router.
- **Read-only in three layers.** The agent sees only the `agent` schema: `agent.transactions`
  and `agent.subscriptions`, thin projections of the dashboard views, without ids, IBANs or raw
  bank descriptions. Every query first passes a `sqlglot` guard (`agent/sql_guard.py`). It then
  runs as the `agent_reader` role in a read-only transaction with a timeout (`agent/sql_runner.py`).
- **Semantic layer.** One YAML file per view, plus metrics and query examples, in
  `apps/api/finance/agent/semantic/`. At startup the YAML is checked against the live views, and
  every metric and example goes through the guard and an `EXPLAIN`. A changed view fails loudly.
- **Middleware.** A turn makes at most 8 queries and 12 model calls. A long chat is summarized at
  150,000 tokens, and old query results leave the request (`ChatSettings` in
  `apps/api/finance/settings.py`).
- **Persistence.** A LangGraph `AsyncPostgresSaver` holds the agent's memory of each chat.
  `chat_threads` and `chat_messages` hold what the UI shows: answers, their queries, status and
  feedback.
- **Transport.** The browser streams with the AI SDK's
  [`useChat`](https://ai-sdk.dev/docs/reference/ai-sdk-ui/use-chat). The agent itself stays in
  Python.
- **Langfuse.** One trace per turn, one session per chat, and scores per turn. A thumbs up or
  down becomes a `user-feedback` score.

The v1 spec's section 9 describes a jev router in front of the chat. That router was not built.
The [slice 4 spec, section 16](superpowers/specs/2026-10-12-slice-4-chat-design.md) is the
amendment.

Known gaps, from [the backlog](backlog.md):
- The agent is told to answer with a figure it queried in the same turn, but nothing checks that
  it did (item 8).
- There are no chat evals (item 6).
- The agent cannot answer balances yet (item 5).

## Money

The category decides whether a row is income, spending or a transfer. Money moved between your
own accounts and money borrowed are neither income nor spending. Every total on every page and
in the chat comes from `v_transactions_enriched`, under the rules in
[money-rules.md](money-rules.md).

## Privacy

The database is local. jev receives the cleaned bank text. The chat model and Langfuse receive
the question, the SQL and the rows it returned: merchant names, amounts, dates, notes and
account names. Neither ever receives an IBAN or a raw bank line.

## Where to read next

| Document | What it is |
|---|---|
| [README](../README.md) | What tally ai does and how to run it |
| [money-rules.md](money-rules.md) | The contract for every total |
| [evals/HISTORY.md](evals/HISTORY.md) | Every categorization benchmark run |
| [jev spike](superpowers/spikes/2026-09-23-jev-categorization/README.md) | Six rounds on real data that set the design and the threshold |
| [Slice 4 spec](superpowers/specs/2026-10-12-slice-4-chat-design.md) | The chat agent as built |
| [v1 spec](superpowers/specs/2026-09-22-personal-finance-agent-v1-design.md) | The original design. Amended: do not read its section 9 as the shipped chat |
| [backlog.md](backlog.md) | Ideas that are designed but not built |

## Limits

- Reads BBVA and CaixaBank PDF statements only.
- Chat figures are not checked against the queries (backlog item 8). There are no chat evals and
  no balances.
- The `public` tables have no row-level security. This is a single-user local app, not a hosted
  one.
````

- [ ] **Step 3: Fact-trace review (subagent)**

Dispatch a reviewer subagent. Do not pass a model override. Give it this brief:
- Trace every figure and mechanism in `README.md` and `docs/architecture.md` to
  `docs/evals/HISTORY.md` or to a `file:line` in the code.
- Return a table with three columns: claim, source, and verdict (`ok`, `wrong`, `untraceable`).
- Check specifically: 397 = 684 − 287; the subscription figures; the level-1 accuracy; the 0.88
  versus 0.75 sentence (it must appear in the spike write-up); the middleware numbers; the 1–4
  word fragments; the list of system rules in the diagram; and that `link_loans` runs after save.

Fix or delete every claim that is not `ok`. Do not soften a wrong claim into a vague one.

- [ ] **Step 4: Resolve every link (one-off, not committed)**

```bash
uv run --no-project python - <<'EOF'
import re, pathlib, sys
bad = []
for page in ["README.md", "docs/architecture.md"]:
    base = pathlib.Path(page).parent
    text = pathlib.Path(page).read_text()
    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        if target.startswith("http"):
            continue
        path, _, anchor = target.partition("#")
        file = (base / path) if path else pathlib.Path(page)
        if not file.exists():
            bad.append(f"{page}: missing {target}")
        elif anchor:
            heads = {re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-")
                     for h in re.findall(r"^#+ (.+)$", file.read_text(), re.M)}
            if anchor not in heads:
                bad.append(f"{page}: no anchor {target}")
print("\n".join(bad) or "all links resolve")
sys.exit(1 if bad else 0)
EOF
```

Expected: `all links resolve`.

- [ ] **Step 5: Read both pages rendered**

Run `gh markdown-preview` if it is installed. Otherwise read the files and check that the Mermaid
blocks are fenced as `mermaid` and the images use the Task 3 paths. Confirm that "99%" appears
only in the sentence about the 254 rows, and "jev router" only in "That router was not built".

- [ ] **Step 6: Commit**

```bash
git add README.md docs/architecture.md
git commit -m "docs: a product README and an architecture page for reviewers"
```

---

### Task 5: Delete the machinery and verify

**Files:**
- Delete: `apps/api/finance/demo_ledger.py`, `apps/api/tests/test_demo_ledger.py`

- [ ] **Step 1: Privacy checks, while `scratch_docs` still exists**

The name check reads the real database (a count, nothing else). Only `SUPABASE_DB_URL` is
taken from the main checkout's `.env`, without echoing it, in this one shell:

```bash
set -a; source <(grep '^SUPABASE_DB_URL=' "<main checkout>/.env"); set +a; \
  cd apps/api && uv run python - <<'PY'
import os
import psycopg
from finance.demo_ledger import build_ledger
names = sorted({r.merchant.upper() for r in build_ledger() if r.merchant})
with psycopg.connect(os.environ["SUPABASE_DB_URL"]) as conn:
    n = conn.execute("select count(*) from merchants where upper(name) = any(%s)", (names,)).fetchone()[0]
print("synthetic names that match a real merchant:", n)
PY
```

Expected: `0`. If it is not 0, rename the colliding synthetic merchant in the generator, update
the Task 1 test if it names it, reload `scratch_docs` (drop, migrate, seed, load), and re-capture
the screenshots that show it. Do not print which real merchant matched.

```bash
git grep -nE 'ES[0-9]{22}' -- README.md docs/architecture.md docs/images || echo "no IBAN in the docs"
```

Expected: `no IBAN in the docs`. A PNG is binary, so this only checks the text. The PNGs were
read in Task 3.

- [ ] **Step 2: Stop the servers and drop the database**

Stop the web and API processes from Task 3, then
`PGHOST=127.0.0.1 PGPORT=54322 PGUSER=postgres PGPASSWORD=postgres dropdb scratch_docs`.

- [ ] **Step 3: Delete the generator and its test**

```bash
git rm apps/api/finance/demo_ledger.py apps/api/tests/test_demo_ledger.py
git grep -n "demo_ledger\|scratch_docs" -- . ':!docs/superpowers' || echo "clean"
```

Expected: `clean`. The spec and this plan mention both by name, and that is fine.

- [ ] **Step 4: Full checks**

Run: `cd apps/api && uv run task test && uv run task lint`
Run: `cd apps/web && npm run lint && npm run build`
Expected: all pass. No web file changed, so the web build is a sanity check.

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: remove the synthetic ledger now that the screenshots exist"
```

- [ ] **Step 6: Whole-branch review and PR handoff**

Run the final whole-branch review (superpowers:requesting-code-review), then
superpowers:finishing-a-development-branch. The PR is squash-merged, so `main` never contains
the generator. The PR description lists:
- the three captures;
- the viewport heights used;
- whether the chat answer was live or replayed;
- the reviewer's fact table;
- that the merchant-collision count was 0.
````
