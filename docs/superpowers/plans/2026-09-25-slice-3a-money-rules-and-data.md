# Slice 3a — Money Rules and Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make income, expenses and savings mean one thing (spec section 2), store it in SQL views, and serve the overview, detail pages, transactions explorer and subscriptions to the web app.

**Architecture:** Categorization changes make `tx_type` follow the category (refunds become negative expenses), add loan and card slugs, and name loans by contract. One view, `v_transactions_enriched`, classifies every row into `spend` and `income`. Thin views aggregate it for the slice 4 agent. The API only filters and sums that view through small modules in `finance/dashboard/`.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic v2, psycopg 3 (dict rows), Supabase Postgres, pytest (`-m integration` for DB tests), Typer CLI.

**Spec:** `docs/superpowers/specs/2026-09-25-slice-3-design.md`. Read sections 2-6, 9-11 and 14 before starting. The v1 spec (`2026-09-22-personal-finance-agent-v1-design.md`) is the baseline this amends.

## Global Constraints

- Everything in English: code, comments, docs, commits.
- Simplicity is a requirement: plain functions, one responsibility per file, no abstraction for a single caller. Follow the existing style (static SQL strings with `%(name)s::type is null or ...` optional filters; never build SQL from user input).
- The row type rule: categorized rows take `categories.tx_type`; uncategorized rows keep the sign rule from import (money in = income, money out = expense).
- Subscriptions are only money-out expense rows (`tx_type = 'expense' and amount < 0`).
- Commands run from `apps/api`: `uv run task test` (unit), `uv run task test-integration` (needs local Supabase + `.env`), `uv run task lint`.
- **Never run `supabase db reset`.** Apply new migrations with `supabase migration up` (from the repo root). Before the first migration, back up labels: `uv run finance labels export` (it refuses to overwrite; that is fine).
- After a migration or a seed change: `uv run finance seed` (from `apps/api`), so integration tests see the new slugs and rules.
- Integration tests write synthetic rows only: dates in 1999, fake IBANs `ES00000000000000000000xx`, text prefixed `ZZTEST`. They run inside a rolled-back transaction (`db_conn`). Never copy real statement text or amounts into tests or docs; the repo is public.
- jev (`typesafe-sdk`) is paid: no task runs `finance categorize` without `--rules-only` or `finance eval-categorization`, except Task 17 with Raul's explicit approval.
- Conventional commits, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Git author is already configured in the repo.
- After any API model change: regenerate the web types with `cd apps/web && npm run gen:api` (API running on :8000).

## Review Focus

1. **An empty ledger or an account with no rows.** The overview must return zeros, `has_previous = false` and 12 months with `has_data = false`, not a 500. Tests: Task 11.
2. **A group whose net spend is negative** (a refund lands after its purchase month). The breakdown must keep it, sort it last, and never divide by a non-positive total. Tests: Task 10.
3. **Search text with `%` or `_`** must match literally, not as wildcards. Tests: Task 12.
4. **Cursor paging over several rows booked on the same day** must never skip or repeat a row. Tests: Task 12.
5. **A labels CSV exported before slice 3** (no `note` column), and a CSV row with an unknown category. The import must still work, and the bad row must be reported by line while the rest import. Tests: Task 8.

## File Structure

| File | Responsibility |
|---|---|
| `supabase/migrations/20260925100000_slice3.sql` | note column, `merchant_source = 'rule'`, rule kinds, `tx_type` recompute |
| `supabase/migrations/20260925110000_slice3_views.sql` | the four views |
| `supabase/seed/categories.yaml`, `rules.yaml` | new slugs, reworded criteria, new rules, refund concepts |
| `finance/categorization/taxonomy.py` | `tx_type_of` by category |
| `finance/categorization/rules.py` | rule kinds, pattern validation, `is_refund` |
| `finance/categorization/seed.py` | disables removed rules |
| `finance/categorization/categorizer.py` | defaults in both directions, refund options, rules-only runs |
| `finance/categorization/loans.py` (new) | loan contract → merchant |
| `finance/categorization/store.py` | rules-only runs, calls `link_loans` |
| `finance/categorization/labels.py` | direction check, unpair on relabel, clear default, notes, no direction filter |
| `finance/categorization/review_queue.py` | a merchant groups both directions |
| `finance/evals/labels_io.py` | notes in the CSV, per-line errors |
| `finance/dashboard/periods.py` (new) | periods and their previous period |
| `finance/dashboard/filters.py` (new) | `Scope`, the shared SQL filter, latest day, has-data |
| `finance/dashboard/models.py` (new) | API response models shared by the routers |
| `finance/dashboard/totals.py` (new) | KPIs, month series, cumulative series |
| `finance/dashboard/breakdowns.py` (new) | group / category / merchant breakdowns, group colour slots |
| `finance/dashboard/transactions.py` (new) | explorer filters, cursor paging, totals |
| `finance/dashboard/subscriptions.py` (new) | active subscriptions and totals |
| `finance/api/periods.py` (new) | the period query parameters as a FastAPI dependency |
| `finance/api/dashboard.py` (new) | `GET /dashboard/overview`, `GET /dashboard/subscriptions` |
| `finance/api/spending.py` (new) | `GET /spending/detail` |
| `finance/api/transactions.py` | explorer list, note `PATCH`, label direction check |
| `finance/api/merchants.py` | `DELETE /merchants/{id}/default`, merge endpoint removed |
| `finance/api/main.py`, `finance/settings.py` | new routers, `TrustedHostMiddleware` |
| `docs/money-rules.md` (new) | the rules for users and agents |
| `apps/web/src/app/transactions/page.tsx` | keeps the current page working on the new response shape |

---

### Task 1: Slice 3 schema migration

**Files:**
- Create: `supabase/migrations/20260925100000_slice3.sql`
- Test: `apps/api/tests/test_schema.py` (append)

**Interfaces:**
- Produces: `transactions.note text` (≤ 500 chars); `transactions.merchant_source` accepts `'rule'`; `rules.kind` (`'categorize' | 'refund'`) with `category_slug` null exactly for `refund` rules.

- [ ] **Step 1: Back up labels (real data safety)**

Run (from `apps/api`): `uv run finance labels export`
Expected: `exported=<n> to .../data/labels/labels-YYYYMMDD.csv`. An "already exists" message is fine: today's backup is there.

- [ ] **Step 2: Write the failing tests**

Append to `apps/api/tests/test_schema.py`:

```python
def test_slice_3_columns_and_checks():
    with connection() as conn:
        assert "note" in _columns(conn, "transactions")
        assert "kind" in _columns(conn, "rules")
        with conn.transaction(force_rollback=True):
            tx = _insert_slice_1_row(conn, "bbva", "ZZTEST NOTE", None)
            conn.execute("update transactions set note = %s where id = %s", ("x" * 500, tx))
            conn.execute("update transactions set merchant_source = 'rule' where id = %s", (tx,))
            with pytest.raises(Exception, match="note"):
                with conn.transaction():
                    conn.execute(
                        "update transactions set note = %s where id = %s", ("x" * 501, tx)
                    )


def test_a_refund_rule_has_no_category_and_a_categorize_rule_needs_one():
    with connection() as conn, conn.transaction(force_rollback=True):
        conn.execute(
            "insert into rules (name, match_field, pattern, direction, kind)"
            " values ('zztest_refund', 'bank_concept', '^X', 'incoming', 'refund')"
        )
        with pytest.raises(Exception, match="rules_kind_category_check"):
            with conn.transaction():
                conn.execute(
                    "insert into rules (name, match_field, pattern, direction)"
                    " values ('zztest_bad', 'bank_concept', '^X', 'incoming')"
                )
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/test_schema.py -m integration -k "slice_3 or refund_rule" -v`
Expected: FAIL (`note` not in columns).

- [ ] **Step 4: Write the migration**

Create `supabase/migrations/20260925100000_slice3.sql`:

```sql
-- Slice 3 (docs/superpowers/specs/2026-09-25-slice-3-design.md, sections 2-4).

-- The user's own account of a row ("AirPods Pro"). jev never sees it; the slice 4 agent does.
alter table transactions add column note text
  constraint transactions_note_length check (char_length(note) <= 500);

-- A system step names the merchant of a loan from its contract number (spec 2.3).
alter table transactions drop constraint transactions_merchant_source_check;
alter table transactions add constraint transactions_merchant_source_check
  check (merchant_source in ('jev', 'user', 'rule', 'none'));

-- A refund rule changes the options jev sees instead of naming a category (spec 2.2).
alter table rules add column kind text not null default 'categorize'
  check (kind in ('categorize', 'refund'));
alter table rules alter column category_slug drop not null;
alter table rules add constraint rules_kind_category_check
  check ((kind = 'categorize') = (category_slug is not null));

-- The row type follows the category, not the sign (spec 2.1). Uncategorized rows keep the
-- sign rule they got at import.
update transactions t set tx_type = c.tx_type, updated_at = now()
from categories c
where c.slug = t.category_slug and t.tx_type <> c.tx_type;

-- Only money going out is a subscription.
update transactions set is_subscription = false where is_subscription and amount > 0;
```

- [ ] **Step 5: Apply it and run the tests**

Run (repo root): `supabase migration up`
Then (from `apps/api`): `uv run pytest tests/test_schema.py -m integration -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/20260925100000_slice3.sql apps/api/tests/test_schema.py
git commit -m "feat: add transaction notes, rule kinds and category-driven row types to the schema"
```

---

### Task 2: The row type follows the category

**Files:**
- Modify: `apps/api/finance/categorization/taxonomy.py:52-55`
- Modify: `apps/api/finance/categorization/labels.py:14-20`
- Test: `apps/api/tests/test_taxonomy.py`, `apps/api/tests/test_labels.py`

**Interfaces:**
- Produces: `Taxonomy.tx_type_of(slug: str, amount: Decimal) -> TxType`. It returns the category's type; `amount` stays in the signature for callers but no longer decides. `labels._TX_TYPE` is the same rule in SQL.

- [ ] **Step 1: Write the failing tests**

In `apps/api/tests/test_taxonomy.py`, append:

```python
def test_the_row_type_follows_the_category_not_the_sign():
    assert TAXONOMY.tx_type_of("fashion", Decimal("80")) == "expense"  # a refund
    assert TAXONOMY.tx_type_of("fashion", Decimal("-80")) == "expense"
    assert TAXONOMY.tx_type_of("salary", Decimal("2000")) == "income"
    assert TAXONOMY.tx_type_of("own_accounts", Decimal("50")) == "transfer"
```

In `apps/api/tests/test_labels.py`, append:

```python
def test_a_money_in_row_labelled_with_an_expense_category_is_a_negative_expense(
    db_conn, make_tx
):
    refund = _tx(make_tx, "80.00", "DEVOLUCION | ZZTEST SHOP")
    label_transaction(db_conn, refund, "fashion", is_subscription=True)
    row = _row(db_conn, refund)
    assert (row["tx_type"], row["is_subscription"]) == ("expense", False)
```

(`_tx` and `_row` are the existing helpers at the top of `test_labels.py`.)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_taxonomy.py -k row_type -v` → FAIL (`'income' != 'expense'`).
Run: `uv run pytest tests/test_labels.py -m integration -k negative_expense -v` → FAIL.

- [ ] **Step 3: Implement**

`taxonomy.py`, replace `tx_type_of`:

```python
    def tx_type_of(self, slug: str, amount: Decimal) -> TxType:
        """The category decides: a money-in row labelled `fashion` is a refund, a negative
        expense (spec 2.1). `amount` is kept for callers; the sign no longer matters."""
        return self._by_slug[slug].tx_type
```

`labels.py`, replace the two constants:

```python
# Taxonomy.tx_type_of in SQL: the category decides the row type (spec 2.1).
_TX_TYPE = "c.tx_type"
# Only money going out is a subscription: never a refund, never a transfer (spec 6).
_SUBSCRIPTION = f"%(sub)s and {_TX_TYPE} = 'expense' and t.amount < 0"
```

In `categorizer.py` `decide()`, replace the subscription line:

```python
    # Only money going out is a subscription: never a refund, never a transfer (spec 6).
    is_subscription = is_subscription and tx_type == "expense" and tx.amount < 0
```

- [ ] **Step 4: Run the unit and integration suites**

Run: `uv run task test` and `uv run pytest tests/test_labels.py tests/test_categorizer.py -m "integration or not integration" -v`
Expected: the new tests PASS. `test_categorizer.py` still passes, because a refund never becomes a subscription.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/categorization/taxonomy.py apps/api/finance/categorization/labels.py apps/api/finance/categorization/categorizer.py apps/api/tests/test_taxonomy.py apps/api/tests/test_labels.py
git commit -m "feat: let the category, not the sign, decide the row type"
```

---

### Task 3: Taxonomy, rules and seed

**Files:**
- Modify: `supabase/seed/categories.yaml`, `supabase/seed/rules.yaml`
- Modify: `apps/api/finance/categorization/rules.py`, `apps/api/finance/categorization/seed.py`, `apps/api/finance/categorization/taxonomy.py:58-59`
- Test: `apps/api/tests/test_rules.py`, `apps/api/tests/test_seed.py` (new, integration)

**Interfaces:**
- Produces:
  - `Rule.kind: Literal["categorize", "refund"]` (default `"categorize"`); `Rule.category_slug: str | None`.
  - `match_rule(...)` returns only `categorize` rules.
  - `is_refund(rules, bank, bank_concept, merchant, direction) -> bool`: True when a `refund` rule matches.
  - `seed(conn) -> tuple[int, int]` also disables rules that are no longer in `rules.yaml`.
  - New slugs `loan_received` (transfer) and `credit_card_spending` (expense, level 1 `credit_card`).

- [ ] **Step 1: Write the failing tests**

In `apps/api/tests/test_rules.py`, update the expected settlement categories in `FIXTURES` and add the new fixtures:

```python
    ("bbva", "ADEUDO MENSUAL DE TARJETA", None, "outgoing", "credit_card_spending"),
    ("caixabank", None, "T. VISA CLASSIC", "outgoing", "credit_card_spending"),
    ("bbva", "CARGO POR OPERACION FINANCIADA CON TARJETA", None, "outgoing", "credit_card_spending"),
    ("bbva", "ABONO POR DISPOSICION DE PRESTAMO/CREDITO", None, "incoming", "loan_received"),
    ("bbva", "CARGO POR AMORTIZACION DE PRESTAMO/CREDITO", None, "outgoing", "loan_payment"),
    ("bbva", "PAGO CON TARJETA EN MODA", "ZZTEST SHOP", "incoming", None),
```

(Replace the two existing `credit_card_payment` lines; keep the other fixtures as they are.)

Append:

```python
from finance.categorization.rules import Rule, is_refund


def test_a_card_purchase_coming_back_is_a_refund():
    assert is_refund(RULES, "bbva", "PAGO CON TARJETA EN MODA", "ZZTEST SHOP", "incoming")
    assert not is_refund(RULES, "bbva", "PAGO CON TARJETA EN MODA", "ZZTEST SHOP", "outgoing")
    assert not is_refund(RULES, "bbva", "TRANSFERENCIA", "ZZTEST ANA", "incoming")


def test_a_refund_rule_never_categorizes():
    refunds = [rule for rule in RULES if rule.kind == "refund"]
    assert refunds and all(rule.category_slug is None for rule in refunds)
    assert match_rule(refunds, "bbva", "PAGO CON TARJETA EN MODA", None, "incoming") is None


@pytest.mark.parametrize(
    "item",
    [
        {"name": "x", "match_field": "merchant", "pattern": "(", "direction": "any",
         "category_slug": "groceries"},
        {"name": "x", "match_field": "merchant", "pattern": "^A", "direction": "any"},
        {"name": "x", "match_field": "merchant", "pattern": "^A", "direction": "any",
         "kind": "refund", "category_slug": "groceries"},
    ],
    ids=["bad-regex", "categorize-without-slug", "refund-with-slug"],
)
def test_invalid_rules_are_refused_when_loaded(item):
    with pytest.raises(ValueError):
        Rule.model_validate(item)
```

Create `apps/api/tests/test_seed.py`:

```python
import pytest

from finance.categorization.seed import seed

pytestmark = pytest.mark.integration


def test_seed_disables_a_rule_removed_from_the_yaml(db_conn):
    db_conn.execute(
        "insert into rules (name, match_field, pattern, direction, category_slug)"
        " values ('zztest_gone', 'merchant', '^ZZTEST', 'any', 'groceries')"
    )
    seed(db_conn)
    row = db_conn.execute("select enabled from rules where name = 'zztest_gone'").fetchone()
    assert row["enabled"] is False
    kept = db_conn.execute(
        "select enabled, kind from rules where name = 'card_refund_concept'"
    ).fetchone()
    assert (kept["enabled"], kept["kind"]) == (True, "refund")


def test_seed_adds_the_slice_3_slugs(db_conn):
    seed(db_conn)
    rows = db_conn.execute(
        "select slug, tx_type, level1 from categories"
        " where slug in ('loan_received', 'credit_card_spending') order by slug"
    ).fetchall()
    assert [tuple(r.values()) for r in rows] == [
        ("credit_card_spending", "expense", "credit_card"),
        ("loan_received", "transfer", "transfer"),
    ]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_rules.py -v` → FAIL (import error `is_refund`).

- [ ] **Step 3: Update the seed data**

`supabase/seed/categories.yaml`: under `expense:`, after the `other:` group, append the new group. Under `income > income`, reword `refunds`. Under `transfer > transfer`, reword `credit_card_payment` and append `loan_received`:

```yaml
  credit_card:
    credit_card_spending:
      what: the monthly settlement of a credit card, or the instalment of a card purchase paid in instalments, when the card's own purchases are not imported (adeudo mensual de tarjeta, operacion financiada con tarjeta)
      not_for: a purchase paid by card at a shop, which takes the shop's category
```

```yaml
    refunds:
      what: money back with no known purchase behind it, such as cashback or a bonus paid by a bank
      not_for: the refund of a purchase at a shop, which takes the category of that purchase
```

```yaml
    credit_card_payment:
      what: monthly settlement of a credit card whose own statement is imported, so its purchases are already categorized
    loan_received:
      what: money a bank or lender pays into the account as a loan or credit line; it is paid back, so it is not income
      not_for: salary, refunds or payments from people
```

Keep every other entry unchanged, and keep the new slugs at the end of their type, so the order jev sees keeps its meaning.

`supabase/seed/rules.yaml`: change `category_slug` of `card_settlement_concept` and `card_settlement_text` to `credit_card_spending`, and append:

```yaml
- {name: card_instalment_concept, match_field: bank_concept, pattern: '^CARGO POR OPERACION FINANCIADA CON TARJETA', direction: outgoing, category_slug: credit_card_spending}
- {name: loan_disbursement_concept, match_field: bank_concept, pattern: '^ABONO POR DISPOSICION DE PRESTAMO', direction: incoming, category_slug: loan_received}
- {name: loan_repayment_concept, match_field: bank_concept, pattern: '^CARGO POR AMORTIZACION DE PRESTAMO', direction: outgoing, category_slug: loan_payment}
# Refund rules name no category: a card purchase coming back is a refund, so jev picks among
# expense categories for it (spec 2.2).
- {name: card_refund_concept, match_field: bank_concept, pattern: '^PAGO CON TARJETA', direction: incoming, kind: refund}
```

- [ ] **Step 4: Implement rule kinds, validation and the seed sync**

`rules.py`, replace the model, readers and matcher:

```python
class Rule(BaseModel):
    name: str
    bank: Bank | None = None
    match_field: Literal["bank_concept", "merchant"]
    pattern: str
    direction: Literal["outgoing", "incoming", "any"]
    kind: Literal["categorize", "refund"] = "categorize"
    category_slug: str | None = None

    @field_validator("pattern")
    @classmethod
    def _compiles(cls, pattern: str) -> str:
        re.compile(pattern)  # a bad regex fails at load, not on the first matching row
        return pattern

    @model_validator(mode="after")
    def _slug_matches_kind(self) -> "Rule":
        if (self.kind == "categorize") != (self.category_slug is not None):
            raise ValueError(f"rule {self.name}: a categorize rule needs a category, a refund rule has none")
        return self


def read_rules_yaml(path: Path) -> list[Rule]:
    return [Rule.model_validate(item) for item in yaml.safe_load(path.read_text(encoding="utf-8"))]


def load_rules(conn: Connection) -> list[Rule]:
    rows = conn.execute(
        "select name, bank, match_field, pattern, direction, kind, category_slug from rules"
        " where enabled order by name"
    ).fetchall()
    return [Rule.model_validate(row) for row in rows]


def _matches(rule: Rule, bank: Bank, bank_concept: str | None, merchant: str | None, direction: Direction) -> bool:
    if rule.bank not in (None, bank) or rule.direction not in ("any", direction):
        return False
    text = bank_concept if rule.match_field == "bank_concept" else merchant
    return bool(text and re.search(rule.pattern, text, re.IGNORECASE))


def match_rule(
    rules: list[Rule],
    bank: Bank,
    bank_concept: str | None,
    merchant: str | None,
    direction: Direction,
) -> Rule | None:
    for rule in rules:
        if rule.kind == "categorize" and _matches(rule, bank, bank_concept, merchant, direction):
            return rule
    return None


def is_refund(
    rules: list[Rule],
    bank: Bank,
    bank_concept: str | None,
    merchant: str | None,
    direction: Direction,
) -> bool:
    """A card purchase coming back (spec 2.2): jev then sees expense categories."""
    return any(
        rule.kind == "refund" and _matches(rule, bank, bank_concept, merchant, direction)
        for rule in rules
    )
```

Add `field_validator, model_validator` to the pydantic import. Pydantic wraps the `re.error` in a `ValidationError`, which is a `ValueError`, so the test passes.

`taxonomy.py:59`: read with `path.read_text(encoding="utf-8")`.

`seed.py`, replace the rules loop and add the disable step:

```python
        for r in rules:
            conn.execute(
                "insert into rules (name, bank, match_field, pattern, direction, kind,"
                " category_slug, enabled) values (%s, %s, %s, %s, %s, %s, %s, true)"
                " on conflict (name) do update set bank = excluded.bank,"
                " match_field = excluded.match_field, pattern = excluded.pattern,"
                " direction = excluded.direction, kind = excluded.kind,"
                " category_slug = excluded.category_slug, enabled = true",
                (r.name, r.bank, r.match_field, r.pattern, r.direction, r.kind, r.category_slug),
            )
        # A rule removed from rules.yaml must stop running, not linger enabled.
        conn.execute(
            "update rules set enabled = false where not (name = any(%s))",
            ([r.name for r in rules],),
        )
```

Update the module docstring to: `"""Sync the taxonomy and system rules from supabase/seed (run after every migration)."""`

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_rules.py -v` → PASS.
Run: `uv run finance seed`, then `uv run pytest tests/test_seed.py -m integration -v` → PASS.
Run: `uv run task test` → PASS. If `test_jev_questions.py` or `test_eval_run.py` pin the exact category count or fingerprint, update the expected number to the new taxonomy: +1 expense leaf, +1 transfer leaf.

- [ ] **Step 6: Commit**

```bash
git add supabase/seed apps/api/finance/categorization/rules.py apps/api/finance/categorization/seed.py apps/api/finance/categorization/taxonomy.py apps/api/tests/test_rules.py apps/api/tests/test_seed.py
git commit -m "feat: add loan and unitemized card slugs, refund rules and a seed that disables removed rules"
```

---

### Task 4: Categorizer — defaults in both directions, refund options, rules-only runs

**Files:**
- Modify: `apps/api/finance/categorization/categorizer.py`
- Test: `apps/api/tests/test_categorizer.py`

**Interfaces:**
- Consumes: `is_refund` (Task 3).
- Produces:
  - `category_options(tx: TxInput, ctx: CategorizationContext) -> list[Category]`.
  - `categorize(rows, ctx, jev: Jev | None, roster, *, use_merchant_defaults=True)`. With `jev=None`, it returns only pairing and rule results and never calls jev.

- [ ] **Step 1: Write the failing tests**

In `apps/api/tests/test_categorizer.py`, **replace** `test_expense_default_does_not_apply_to_a_refund` with:

```python
def test_a_merchant_default_applies_to_a_refund_too():
    roster = MerchantRoster([MerchantRef(id=uuid4(), name="ACME", category_slug="fashion")])
    refund = jev_result(
        merchant={"ACME": 0.97, "none": 0.03}, category={"fashion": 0.6, "home_goods": 0.4}
    )
    [result] = _run([_tx("ACME", amount="13.77")], FakeJev(first={"ACME": refund}), roster)
    assert (result.category_slug, result.category_source, result.tx_type) == (
        "fashion",
        "merchant",
        "expense",
    )
```

Append:

```python
from finance.categorization.categorizer import category_options


def test_a_card_purchase_coming_back_is_offered_expense_categories():
    refund = _tx("ACME", amount="13.77", concept="PAGO CON TARJETA EN MODA")
    slugs = {c.slug for c in category_options(refund, CTX)}
    assert "fashion" in slugs and "salary" not in slugs


def test_other_money_in_keeps_the_income_options():
    salary = _tx("ACME PAYROLL", amount="2000", concept="TRANSFERENCIA")
    slugs = {c.slug for c in category_options(salary, CTX)}
    assert "salary" in slugs and "fashion" not in slugs


def test_without_jev_only_pairing_and_rule_rows_come_back():
    settlement = _tx("", amount="-175.00", concept="ADEUDO MENSUAL DE TARJETA")
    shop = _tx("ACME")
    results = asyncio.run(categorize([settlement, shop], CTX, None, MerchantRoster([])))
    assert [(r.transaction_id, r.category_slug) for r in results] == [
        (settlement.id, "credit_card_spending")
    ]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_categorizer.py -v`
Expected: FAIL (`category_options` missing; the default test still gets `refunds`).

- [ ] **Step 3: Implement**

In `categorizer.py`:

```python
from finance.categorization.rules import Rule, is_refund, match_rule
from finance.categorization.taxonomy import Category, Taxonomy, direction_of


def category_options(tx: TxInput, ctx: CategorizationContext) -> list[Category]:
    """The options jev picks from: the row's direction, except that a card purchase coming
    back is a refund and takes an expense category (spec 2.2)."""
    direction = direction_of(tx.amount)
    if direction == "incoming" and is_refund(
        ctx.rules, tx.bank, tx.bank_concept, tx.merchant, direction
    ):
        return ctx.taxonomy.leaves("outgoing")
    return ctx.taxonomy.leaves(direction)
```

In `decide()`, delete `direction = direction_of(tx.amount)`, and replace the default block with:

```python
    if use_merchant_defaults and merchant:
        # A default applies in both directions: a shop's refunds take its category (spec 2.2).
        if merchant.category_slug:
            slug, source = merchant.category_slug, "merchant"
            confidence = level1_confidence = None
        if merchant.is_subscription is not None:
            is_subscription = merchant.is_subscription
```

In `categorize()`:
- change the type to `jev: Jev | None`;
- after the rule loop, add `if jev is None: return [results[tx.id] for tx in rows if tx.id in results]`;
- in the `gather`, replace `ctx.taxonomy.leaves(direction_of(tx.amount))` with `category_options(tx, ctx)`;
- inside the first loop, replace the `direction` variable with a direct call: `match_rule(ctx.rules, tx.bank, tx.bank_concept, tx.merchant, direction_of(tx.amount))`.

Update the docstring: "With `jev=None` only pairing and rule rows come back: a rules-only run."

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_categorizer.py -v` → PASS. Then `uv run task test` → PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/categorization/categorizer.py apps/api/tests/test_categorizer.py
git commit -m "feat: apply merchant defaults to refunds and offer expense categories for card refunds"
```

---

### Task 5: Rules-only runs and loan merchants

**Files:**
- Create: `apps/api/finance/categorization/loans.py`
- Modify: `apps/api/finance/categorization/store.py`, `apps/api/finance/cli.py:61-68`
- Test: `apps/api/tests/test_loans.py` (new), `apps/api/tests/test_store.py`, `apps/api/tests/test_cli.py`

**Interfaces:**
- Consumes: `categorize(..., jev=None)` (Task 4), `get_or_create_merchant` (labels).
- Produces:
  - `loan_merchant_name(description_raw: str) -> str | None`.
  - `link_loans(conn) -> int`.
  - `categorize_pending(conn, settings, include_all=False, jev=None, rules_only=False)`.
  - `run_categorization(include_all=False, rules_only=False)`.
  - The CLI flag `finance categorize --rules-only`.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_loans.py`:

```python
from datetime import date

import pytest

from finance.categorization.loans import link_loans, loan_merchant_name

CONTRACT = "0000-1111-22-3333334567"  # synthetic contract number


def test_the_contract_number_names_the_loan():
    assert loan_merchant_name(f"CARGO POR AMORTIZACION DE PRESTAMO/CREDITO | {CONTRACT}") == (
        "Loan ····4567"
    )
    assert loan_merchant_name("CARGO POR AMORTIZACION DE PRESTAMO/CREDITO | ") is None


@pytest.mark.integration
def test_a_disbursement_and_its_instalments_share_one_merchant(db_conn, make_tx):
    rows = [
        make_tx("1500.00", f"ABONO POR DISPOSICION DE PRESTAMO/CREDITO | {CONTRACT}",
                booked_at=date(1999, 1, 5)),
        make_tx("-130.00", f"CARGO POR AMORTIZACION DE PRESTAMO/CREDITO | {CONTRACT}",
                booked_at=date(1999, 2, 5)),
    ]
    for tx, slug in zip(rows, ["loan_received", "loan_payment"], strict=True):
        db_conn.execute(
            "update transactions set category_slug = %s, category_source = 'rule' where id = %s",
            (slug, tx),
        )
    assert link_loans(db_conn) == 2
    found = db_conn.execute(
        "select distinct t.merchant_id, t.merchant_source, m.name from transactions t"
        " join merchants m on m.id = t.merchant_id where t.id = any(%s)",
        (rows,),
    ).fetchall()
    assert [(r["merchant_source"], r["name"]) for r in found] == [("rule", "Loan ····4567")]


@pytest.mark.integration
def test_a_renamed_loan_keeps_its_new_instalments(db_conn, make_tx):
    first = make_tx("-130.00", f"CARGO POR AMORTIZACION DE PRESTAMO/CREDITO | {CONTRACT}",
                    booked_at=date(1999, 2, 5))
    db_conn.execute("update transactions set category_slug = 'loan_payment' where id = %s", (first,))
    link_loans(db_conn)
    db_conn.execute(
        "update merchants set name = 'ZZTEST car loan', match_key = 'ZZTESTCARLOAN'"
        " where id = (select merchant_id from transactions where id = %s)",
        (first,),
    )
    later = make_tx("-130.00", f"CARGO POR AMORTIZACION DE PRESTAMO/CREDITO | {CONTRACT}",
                    booked_at=date(1999, 3, 5))
    db_conn.execute("update transactions set category_slug = 'loan_payment' where id = %s", (later,))
    link_loans(db_conn)
    names = db_conn.execute(
        "select distinct m.name from transactions t join merchants m on m.id = t.merchant_id"
        " where t.id = any(%s)",
        ([first, later],),
    ).fetchall()
    assert [r["name"] for r in names] == ["ZZTEST car loan"]
```

In `apps/api/tests/test_store.py`, append:

```python
def test_without_a_jev_key_rules_still_apply(db_conn, make_tx):
    settlement = make_tx(
        "-175.00", "ADEUDO MENSUAL DE TARJETA | ZZTEST", bank_concept="ADEUDO MENSUAL DE TARJETA",
        booked_at=SYNTHETIC_DAY,
    )
    shop = make_tx("-9.90", "PAGO | ZZTEST ACME", merchant="ZZTEST ACME", booked_at=SYNTHETIC_DAY)
    summary = asyncio.run(categorize_pending(db_conn, Settings(typesafe_api_key=None)))
    assert summary.skipped and summary.by_source.get("rule", 0) >= 1
    assert _source(db_conn, settlement) == "rule"
    assert _source(db_conn, shop) == "none"


def test_a_rules_only_run_never_calls_jev(db_conn, make_tx):
    make_tx("-9.90", "PAGO | ZZTEST ACME", merchant="ZZTEST ACME", booked_at=SYNTHETIC_DAY)
    jev = FakeJev()
    asyncio.run(categorize_pending(db_conn, Settings(), jev=jev, rules_only=True))
    assert jev.calls == []
```

In `apps/api/tests/test_cli.py`:
- change every `lambda include_all=False:` stub and the `_run(include_all=False)` helper to also accept `rules_only=False`;
- in `test_categorize_all_reruns_everything_and_prints_the_counts`, record `(include_all, rules_only)` and assert `calls == [(True, False)]`;
- append:

```python
def test_categorize_rules_only_passes_the_flag(monkeypatch):
    calls = []

    def _run(include_all=False, rules_only=False):
        calls.append((include_all, rules_only))
        return CategorizeSummary(categorized=1, by_source={"rule": 1})

    monkeypatch.setattr(cli, "run_categorization", _run)
    result = runner.invoke(cli.app, ["categorize", "--all", "--rules-only"])
    assert result.exit_code == 0 and calls == [(True, True)]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_loans.py tests/test_store.py tests/test_cli.py -m "integration or not integration" -v`
Expected: FAIL (`finance.categorization.loans` missing; no `rules_only`).

- [ ] **Step 3: Implement `loans.py`**

```python
"""One loan = one merchant: the contract number on its bank lines names it (spec 2.3)."""

import re

from psycopg import Connection

from finance.categorization.labels import get_or_create_merchant

# BBVA prints a loan's contract number like an account number: 4-4-2-10 digits.
CONTRACT = re.compile(r"\b\d{4}-\d{4}-\d{2}-\d{10}\b")
LOAN_SLUGS = ["loan_received", "loan_payment"]


def loan_merchant_name(description_raw: str) -> str | None:
    match = CONTRACT.search(description_raw)
    return f"Loan ····{match.group()[-4:]}" if match else None


def link_loans(conn: Connection) -> int:
    """Give every loan row without a merchant the merchant of its contract. A row of the same
    contract already linked wins, so a loan the user renamed keeps its new instalments."""
    rows = conn.execute(
        "select id, description_raw from transactions"
        " where category_slug = any(%s) and merchant_id is null",
        (LOAN_SLUGS,),
    ).fetchall()
    linked = 0
    for row in rows:
        match = CONTRACT.search(row["description_raw"])
        if match is None:
            continue
        known = conn.execute(
            "select merchant_id from transactions where merchant_id is not null"
            " and category_slug = any(%s) and strpos(description_raw, %s) > 0 limit 1",
            (LOAN_SLUGS, match.group()),
        ).fetchone()
        merchant_id = (
            known["merchant_id"] if known else get_or_create_merchant(conn, loan_merchant_name(row["description_raw"]))
        )
        conn.execute(
            "update transactions set merchant_id = %s, merchant_source = 'rule', updated_at = now()"
            " where id = %s",
            (merchant_id, row["id"]),
        )
        linked += 1
    return linked
```

- [ ] **Step 4: Implement rules-only runs in `store.py`**

Replace `categorize_pending` and `run_categorization`:

```python
async def categorize_pending(
    conn: Connection,
    settings: Settings,
    include_all: bool = False,
    jev: Jev | None = None,
    rules_only: bool = False,
) -> CategorizeSummary:
    paired = pair_transfers(conn, settings)
    rows = load_pending(conn, include_all)
    skipped = None
    if jev is None and not rules_only and not settings.typesafe_api_key:
        rules_only, skipped = True, "TYPESAFE_API_KEY is not set"
    if not rows:
        link_loans(conn)
        return CategorizeSummary(paired=paired, skipped=skipped)
    ctx = CategorizationContext(load_taxonomy(conn), load_rules(conn), settings)
    roster = load_roster(conn)
    if rules_only:
        # Pairing and rules only: no jev call, so no cost (spec 3).
        results = await categorize(rows, ctx, None, roster)
        failed = 0
    else:
        # One trace per run: every jev generation nests under this span.
        with langfuse().start_as_current_observation(as_type="span", name="categorize") as span:
            if jev is None:
                async with TypesafeJev(
                    settings.typesafe_api_key, concurrency=settings.jev_concurrency
                ) as client:
                    results = await categorize(rows, ctx, client, roster)
            else:
                results = await categorize(rows, ctx, jev, roster)
            span.update(output={"categorized": len(results)})
        failed = len(rows) - len(results)
    summary = CategorizeSummary(
        paired=paired,
        categorized=len(results),
        needs_review=sum(r.needs_review for r in results),
        by_source=dict(Counter(r.category_source for r in results)),
        failed=failed,
        skipped=skipped,
    )
    save(conn, results, roster)
    link_loans(conn)
    return summary


def run_categorization(include_all: bool = False, rules_only: bool = False) -> CategorizeSummary:
    with connection() as conn:
        return asyncio.run(categorize_pending(conn, get_settings(), include_all, rules_only=rules_only))
```

Update `CategorizeSummary.line()`, so that a skipped run still shows the rule rows:

```python
    def line(self) -> str:
        counts = [f"paired={self.paired}"] + [
            f"{source}={n}" for source, n in sorted(self.by_source.items())
        ]
        if self.skipped:
            return f"categorization skipped: {self.skipped} ({' '.join(counts)})"
        parts = [counts[0], f"categorized={self.categorized}", *counts[1:]]
        parts.append(f"needs_review={self.needs_review}")
        if self.failed:
            parts.append(f"failed={self.failed}")
        return " ".join(parts)
```

(`test_categorize_says_why_it_skipped` still expects `(paired=2)`, because `by_source` is empty there.) Add `from finance.categorization.loans import link_loans`.

In `cli.py`, add the option and pass it:

```python
@app.command("categorize")
def categorize_command(
    include_all: bool = typer.Option(
        False, "--all", help="Re-run every transaction you have not labelled yourself."
    ),
    rules_only: bool = typer.Option(
        False, "--rules-only", help="Pairing and system rules only: never calls jev."
    ),
) -> None:
    """Categorize pending transactions (pairing, rules, jev)."""
    typer.echo(run_categorization(include_all, rules_only).line())
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_loans.py tests/test_store.py tests/test_cli.py -m "integration or not integration" -v` → PASS. Then `uv run task test` → PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/categorization/loans.py apps/api/finance/categorization/store.py apps/api/finance/cli.py apps/api/tests/test_loans.py apps/api/tests/test_store.py apps/api/tests/test_cli.py
git commit -m "feat: name loans by contract and apply rules without jev"
```

---

### Task 6: Review groups a merchant's rows in both directions

**Files:**
- Modify: `apps/api/finance/categorization/review_queue.py:95-101`, `apps/api/finance/categorization/labels.py:33-42`
- Test: `apps/api/tests/test_review_queue.py`, `apps/api/tests/test_review_api.py`, `apps/api/tests/test_labels.py`

**Interfaces:**
- Produces: a merchant review item holds all of the merchant's pending rows, whatever their sign. `confirm_merchant` relabels them all (except user rows).

- [ ] **Step 1: Rewrite the tests that pin the old rule**

`tests/test_review_queue.py`, replace `test_a_refund_of_a_merchant_with_an_expense_default_stands_alone` with:

```python
def test_a_refund_joins_its_merchant_item():
    merge = MergeSuggestion(merchant_id=uuid4(), name="ACME FOODS", confidence=0.6)
    rows = [
        _row("-20", ACME, {"groceries": 0.8, "restaurants_bars": 0.2}, default="groceries"),
        _row("15", ACME, {"groceries": 0.7, "restaurants_bars": 0.3}, default="groceries"),
    ]
    [item] = build_review_items(rows, {ACME: merge}, TAXONOMY)
    assert (item.key, item.kind, item.count, item.total) == (f"m:{ACME}", "merchant", 2, Decimal("-5"))
    assert item.merge == merge
```

`tests/test_review_api.py`, replace `test_a_refund_of_a_merchant_with_an_expense_default_is_its_own_item` with:

```python
def test_a_refund_is_reviewed_with_its_merchant(client, db_conn, make_tx):
    acme = _merchant(db_conn, "ZZTEST ACME", category_slug="groceries")
    refund = make_tx("12.50", "DEVOLUCION | ZZTEST ACME", booked_at=SYNTHETIC_DAY)
    _to_review(db_conn, refund, "groceries", merchant_id=acme)
    keys = _keys(client)
    assert f"m:{acme}" in keys and f"t:{refund}" not in keys
```

`tests/test_labels.py` `test_confirm_sets_the_default_and_relabels_reviewed_rows`: change the assertion `assert _row(db_conn, refund)["category_slug"] == "refunds"` to:

```python
    refund_row = _row(db_conn, refund)
    assert (refund_row["category_slug"], refund_row["tx_type"]) == ("restaurants_bars", "expense")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_review_queue.py -v` → FAIL. Integration: `uv run pytest tests/test_review_api.py tests/test_labels.py -m integration -v` → FAIL.

- [ ] **Step 3: Implement**

`review_queue.py`, replace `_joins_its_merchant`:

```python
def _joins_its_merchant(row: ReviewRow) -> bool:
    """Every row of a merchant, purchases and refunds alike, is reviewed as one item: a refund
    takes the purchase's category (spec 2.2)."""
    return row.merchant_id is not None
```

Update the call in `build_review_items` to `_joins_its_merchant(row)`. Remove imports that are now unused (`direction_of`, and `Taxonomy` if unused); `ruff` will flag them.

`labels.py` `_RELABEL_MERCHANT`: delete the line `and c.tx_type in ('transfer', case when t.amount < 0 then 'expense' else 'income' end)`.

- [ ] **Step 4: Run the tests**

Run: `uv run task test` and `uv run pytest tests/test_review_api.py tests/test_labels.py tests/test_review_queue.py -m "integration or not integration" -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/categorization/review_queue.py apps/api/finance/categorization/labels.py apps/api/tests
git commit -m "feat: review and confirm a merchant's purchases and refunds together"
```

---

### Task 7: Label rules — direction check, unpairing, clearing a default, notes

**Files:**
- Modify: `apps/api/finance/categorization/labels.py`, `apps/api/finance/api/transactions.py`, `apps/api/finance/api/merchants.py`
- Test: `apps/api/tests/test_labels.py`, `apps/api/tests/test_review_api.py`

**Interfaces:**
- Produces:
  - `class DirectionMismatch(ValueError)`: raised by `label_transaction` for money out labelled with an income category, and by `confirm_merchant` for an income default on a merchant with money-out rows.
  - `clear_merchant_default(conn, merchant_id) -> None`.
  - `set_note(conn, transaction_id, note: str | None) -> None`.
  - `PATCH /transactions/{id}` with body `{"note": str | null}` → 204.
  - `DELETE /merchants/{id}/default` → 204.
  - `POST /merchants/{id}/merge` is removed.

- [ ] **Step 1: Write the failing tests**

Append to `apps/api/tests/test_labels.py`:

```python
from finance.categorization.labels import DirectionMismatch, clear_merchant_default, set_note


def test_money_out_cannot_take_an_income_category(db_conn, make_tx):
    charge = _tx(make_tx, "-9.90", "PAGO | ZZTEST SHOP")
    with pytest.raises(DirectionMismatch):
        label_transaction(db_conn, charge, "salary", is_subscription=False)


def test_relabelling_one_side_of_a_pair_unpairs_both_and_sends_the_other_to_review(
    db_conn, make_tx
):
    out = _tx(make_tx, "-50.00", "TRASPASO | ZZTEST")
    into = make_tx("50.00", "TRASPASO | ZZTEST", iban="ES0000000000000000000002",
                   booked_at=SYNTHETIC_DAY)
    pair = uuid4()
    for tx in (out, into):
        _set(db_conn, tx, transfer_pair_id=pair, category_slug="own_accounts",
             category_source="rule", tx_type="transfer")
    label_transaction(db_conn, out, "payments_to_people", is_subscription=False)
    assert _row(db_conn, out)["transfer_pair_id"] is None
    other = _row(db_conn, into)
    assert (other["transfer_pair_id"], other["needs_review"]) == (None, True)


def test_clearing_a_default_keeps_the_rows_as_they_are(db_conn, make_tx):
    acme = _merchant(db_conn, "ZZTEST ACME", category_slug="groceries", is_subscription=False)
    clear_merchant_default(db_conn, acme)
    merchant = db_conn.execute("select * from merchants where id = %s", (acme,)).fetchone()
    assert (merchant["category_slug"], merchant["is_subscription"]) == (None, None)
    with pytest.raises(NotFound):
        clear_merchant_default(db_conn, uuid4())


def test_a_note_is_trimmed_and_an_empty_one_is_cleared(db_conn, make_tx):
    tx = _tx(make_tx, "-51.00", "PAGO | ZZTEST SHOP")
    set_note(db_conn, tx, "  AirPods case  ")
    assert _row(db_conn, tx)["note"] == "AirPods case"
    set_note(db_conn, tx, "   ")
    assert _row(db_conn, tx)["note"] is None


def test_a_merchant_with_money_out_cannot_take_an_income_default(db_conn, make_tx):
    acme = _merchant(db_conn, "ZZTEST ACME")
    charge = _tx(make_tx, "-9.90", "PAGO | ZZTEST ACME")
    _set(db_conn, charge, merchant_id=acme, category_source="jev", category_slug="groceries")
    with pytest.raises(DirectionMismatch):
        confirm_merchant(db_conn, acme, "salary", False)


def test_confirming_with_another_merchant_sets_the_survivor_default(db_conn, make_tx):
    """M10: since the review-fix PR the survivor's default is the confirmed category."""
    source = _merchant(db_conn, "ZZTEST ACME SHOP")
    survivor = _merchant(db_conn, "ZZTEST ACME", category_slug="groceries")
    confirm_merchant(db_conn, source, "fashion", False, merge_into_id=survivor)
    row = db_conn.execute("select category_slug from merchants where id = %s", (survivor,)).fetchone()
    assert row["category_slug"] == "fashion"
```

(If `_set` does not already accept arbitrary columns, it follows the `_merchant` pattern at the top of the file: `update transactions set {column} = %s where id = %s` for each keyword.)

Append to `apps/api/tests/test_review_api.py`:

```python
def test_label_rejects_an_income_category_for_money_out(client, make_tx):
    tx = make_tx("-3.00", "ZZTEST SHOP", booked_at=SYNTHETIC_DAY)
    body = {"category_slug": "salary", "is_subscription": False}
    assert client.post(f"/transactions/{tx}/label", json=body).status_code == 422


def test_note_and_default_endpoints(client, db_conn, make_tx):
    tx = make_tx("-3.00", "ZZTEST SHOP", booked_at=SYNTHETIC_DAY)
    assert client.patch(f"/transactions/{tx}", json={"note": "gift"}).status_code == 204
    assert client.patch(f"/transactions/{tx}", json={"note": "x" * 501}).status_code == 422
    assert client.patch(f"/transactions/{MISSING}", json={"note": "x"}).status_code == 404
    acme = _merchant(db_conn, "ZZTEST ACME", category_slug="groceries")
    assert client.delete(f"/merchants/{acme}/default").status_code == 204
    assert client.delete(f"/merchants/{MISSING}/default").status_code == 404
    assert client.post(f"/merchants/{acme}/merge", json={"into_id": MISSING}).status_code in (404, 405)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_labels.py tests/test_review_api.py -m integration -v` → FAIL (imports).

- [ ] **Step 3: Implement in `labels.py`**

```python
class DirectionMismatch(ValueError):
    """Money going out cannot be income (spec 7.3). Money in may take an expense category:
    that is a refund."""


_UNPAIR = """
update transactions set transfer_pair_id = null, needs_review = true, updated_at = now()
where transfer_pair_id = (select transfer_pair_id from transactions where id = %(id)s)
"""
```

In `label_transaction`, inside the transaction and before `_LABEL_ONE`:

```python
        kind = conn.execute(
            "select t.amount, t.transfer_pair_id, c.tx_type from transactions t, categories c"
            " where t.id = %s and c.slug = %s",
            (transaction_id, category_slug),
        ).fetchone()
        if kind and kind["amount"] < 0 and kind["tx_type"] == "income":
            raise DirectionMismatch(f"{category_slug} is income; this transaction is money out")
        if kind and kind["transfer_pair_id"] and category_slug != "own_accounts":
            # Not a transfer after all: both sides unpair and the other goes to review (M13).
            conn.execute(_UNPAIR, {"id": transaction_id})
```

`_LABEL_ONE` sets `needs_review = false` on the labelled row, so only the other side stays in review.

In `confirm_merchant`, after the `if merge_into_id is not None:` block and right before `updated = conn.execute(` (so every confirm runs it, on the survivor's rows after a merge), add:

```python
        income = conn.execute(
            "select 1 from categories c where c.slug = %s and c.tx_type = 'income'"
            " and exists (select 1 from transactions t where t.merchant_id = %s and t.amount < 0"
            " and t.category_source <> 'user')",
            (category_slug, merchant_id),
        ).fetchone()
        if income:
            raise DirectionMismatch(f"{category_slug} is income; this merchant has money out")
```

`review_merchant` already maps `ValueError` to 422. Then add:

```python
def clear_merchant_default(conn: Connection, merchant_id: UUID) -> None:
    """A mixed merchant (spec 7.3): its rows keep their labels; new rows go through jev."""
    row = conn.execute(
        "update merchants set category_slug = null, is_subscription = null where id = %s"
        " returning id",
        (merchant_id,),
    ).fetchone()
    if row is None:
        raise NotFound(f"merchant {merchant_id}")


def set_note(conn: Connection, transaction_id: UUID, note: str | None) -> None:
    """A note is not a label: no label history (spec 4)."""
    text = (note or "").strip() or None
    row = conn.execute(
        "update transactions set note = %s, updated_at = now() where id = %s returning id",
        (text, transaction_id),
    ).fetchone()
    if row is None:
        raise NotFound(f"transaction {transaction_id}")
```

- [ ] **Step 4: Implement the endpoints**

`api/transactions.py`, add:

```python
class NoteUpdate(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.patch("/{transaction_id}", status_code=204)
def update_note(transaction_id: UUID, body: NoteUpdate, conn: Db) -> Response:
    try:
        set_note(conn, transaction_id, body.note)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)
```

`DirectionMismatch` is a `ValueError`, so the existing `except ValueError` in `label()` already maps it to 422.

`api/merchants.py`: delete `MergeRequest` and the `merge` route, and remove `merge_merchants` from the import. Add:

```python
@router.delete("/{merchant_id}/default", status_code=204)
def clear_default(merchant_id: UUID, conn: Db) -> Response:
    try:
        clear_merchant_default(conn, merchant_id)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)
```

If `tests/test_review_api.py` or `test_api.py` still call `POST /merchants/{id}/merge`, delete those tests: the web app merges only through confirm, where the survivor's default is the confirmed category (M10/M11 closed).

- [ ] **Step 5: Run the tests**

Run: `uv run task test` and `uv run pytest -m integration -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance apps/api/tests
git commit -m "feat: check label direction, unpair relabelled transfers, clear defaults and edit notes"
```

---

### Task 8: Labels export/import carry notes and report bad rows

**Files:**
- Modify: `apps/api/finance/evals/labels_io.py`, `apps/api/finance/cli.py:104-110`
- Test: `apps/api/tests/test_labels_io.py`, `apps/api/tests/test_cli.py`

**Interfaces:**
- Produces:
  - CSV columns `dedup_key, category_slug, is_subscription, merchant, note`. A row with a note but no user label has an empty `category_slug`.
  - `LabelsImport(imported, missing, notes, errors: list[str])`.
  - `finance labels import` exits 1 when `errors` is not empty.

- [ ] **Step 1: Write the failing tests**

Append to `apps/api/tests/test_labels_io.py` (it already has `db_conn`, `make_tx`, `tmp_path` usage):

```python
def test_notes_travel_even_without_a_label(db_conn, make_tx, tmp_path):
    tx = make_tx("-51.00", "PAGO | ZZTEST SHOP", booked_at=date(1999, 1, 1))
    db_conn.execute("update transactions set note = 'AirPods case' where id = %s", (tx,))
    path = tmp_path / "labels.csv"
    export_labels(db_conn, path)
    db_conn.execute("update transactions set note = null where id = %s", (tx,))
    result = import_labels(db_conn, path)
    assert result.notes >= 1
    assert db_conn.execute("select note from transactions where id = %s", (tx,)).fetchone()["note"] == "AirPods case"


def test_an_old_csv_imports_and_a_bad_row_is_reported_by_line(db_conn, make_tx, tmp_path):
    good = make_tx("-9.90", "PAGO | ZZTEST ACME", booked_at=date(1999, 1, 1))
    key = db_conn.execute("select dedup_key from transactions where id = %s", (good,)).fetchone()["dedup_key"]
    path = tmp_path / "old.csv"
    path.write_text(
        "dedup_key,category_slug,is_subscription,merchant\n"
        f"{key},groceries,false,ZZTEST ACME\n"
        f"{key},no_such_category,false,\n"
    )
    result = import_labels(db_conn, path)
    assert result.imported == 1
    assert len(result.errors) == 1 and result.errors[0].startswith("line 3:")
```

(Add `from datetime import date` if the file lacks it.)

In `apps/api/tests/test_cli.py`, append:

```python
def test_labels_import_exits_one_and_prints_bad_rows(monkeypatch, tmp_path):
    source = tmp_path / "labels.csv"
    source.write_text("dedup_key,category_slug,is_subscription,merchant\n")
    monkeypatch.setattr(cli, "connection", lambda: nullcontext(None))
    monkeypatch.setattr(
        cli,
        "import_labels",
        lambda conn, path: LabelsImport(imported=1, missing=0, errors=["line 3: unknown category"]),
    )
    result = runner.invoke(cli.app, ["labels", "import", str(source)])
    assert result.exit_code == 1
    assert "line 3: unknown category" in result.output
```

(Assert on the error stream the same way `test_import_reports_a_bad_file_and_continues_with_the_rest` does; switch `result.output` to that attribute if it differs.)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_labels_io.py tests/test_cli.py -m "integration or not integration" -v` → FAIL.

- [ ] **Step 3: Implement**

`labels_io.py`:

```python
FIELDS = ("dedup_key", "category_slug", "is_subscription", "merchant", "note")

_EXPORT = """
with labels as (
  select distinct on (l.transaction_id) l.transaction_id, l.category_slug, l.is_subscription,
         coalesce(m.name, '') as merchant
  from transaction_labels l
  left join merchants m on m.id = l.merchant_id
  where l.source = 'user'
  order by l.transaction_id, l.labeled_at desc
)
select t.dedup_key, coalesce(lb.category_slug, '') as category_slug,
       coalesce(lb.is_subscription::text, '') as is_subscription,
       coalesce(lb.merchant, '') as merchant, coalesce(t.note, '') as note
from transactions t
left join labels lb on lb.transaction_id = t.id
where lb.transaction_id is not null or t.note is not null
order by t.dedup_key
"""


class LabelsImport(BaseModel):
    imported: int
    missing: int
    notes: int = 0
    errors: list[str] = []


def import_labels(conn: Connection, path: Path) -> LabelsImport:
    """A CSV exported before slice 3 has no note column. A bad row is reported by its line
    number and skipped; the others still import."""
    result = LabelsImport(imported=0, missing=0)
    with path.open(newline="", encoding="utf-8") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            found = conn.execute(
                "select id from transactions where dedup_key = %s", (row["dedup_key"],)
            ).fetchone()
            if found is None:
                result.missing += 1
                continue
            try:
                if row["category_slug"]:
                    label_transaction(
                        conn,
                        found["id"],
                        row["category_slug"],
                        row["is_subscription"].strip().lower() in ("1", "true"),
                        new_merchant_name=row["merchant"] or None,
                    )
                    result.imported += 1
                if row.get("note"):
                    set_note(conn, found["id"], row["note"])
                    result.notes += 1
            except (NotFound, ValueError) as error:
                result.errors.append(f"line {line}: {error}")
    return result
```

Imports: `from finance.categorization.labels import NotFound, label_transaction, set_note`. An unknown category makes `_LABEL_ONE` return no row, so `label_transaction` raises `NotFound`. That exception is raised inside `label_transaction`'s own `conn.transaction()`, so only that row rolls back.

`cli.py` `labels_import`:

```python
    typer.echo(f"imported={result.imported} missing={result.missing} notes={result.notes}")
    for error in result.errors:
        typer.echo(error, err=True)
    if result.errors:
        raise typer.Exit(code=1)
```

Update `test_labels_import_prints_the_counts` to expect `"imported=2 missing=1 notes=0"`.

- [ ] **Step 4: Run the tests**

Run: `uv run task test` and `uv run pytest tests/test_labels_io.py -m integration -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/evals/labels_io.py apps/api/finance/cli.py apps/api/tests
git commit -m "feat: keep notes in the labels CSV and report bad rows by line"
```

---

### Task 9: The views and `docs/money-rules.md`

**Files:**
- Create: `supabase/migrations/20260925110000_slice3_views.sql`, `docs/money-rules.md`
- Test: `apps/api/tests/test_views.py` (new, integration), `apps/api/tests/money_month.py` (new fixture helper)

**Interfaces:**
- Produces:
  - `v_transactions_enriched` columns: `id, account_id, account_name, bank, booked_at, month, amount, currency, direction, tx_type, category_slug, level1, category_source, merchant_id, merchant_name, bank_merchant_text, description_raw, bank_concept, note, is_subscription, needs_review, transfer_pair_id, spend, income`.
  - `v_monthly_summary(month, account_id, income, expenses, savings, row_count)`.
  - `v_spend_by_category(month, account_id, level1, category_slug, merchant_id, merchant_name, spend, row_count)`.
  - `v_subscriptions(merchant_id, merchant_name, charges, last_charge, typical_amount, cadence, monthly_equivalent, active)`.
  - The test helper `money_month(db_conn, make_tx) -> UUID` (the account id).

- [ ] **Step 1: Write the fixture helper**

Create `apps/api/tests/money_month.py`:

```python
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
```

- [ ] **Step 2: Write the failing tests**

Create `apps/api/tests/test_views.py`:

```python
from decimal import Decimal

import pytest

from tests.money_month import money_month

pytestmark = pytest.mark.integration


def test_monthly_summary_follows_the_money_rules(db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    rows = db_conn.execute(
        "select month, income, expenses, savings from v_monthly_summary"
        " where account_id = %s order by month",
        (account,),
    ).fetchall()
    assert [tuple(r.values()) for r in rows] == [
        ("1999-01", Decimal("2000.00"), Decimal("455.00"), Decimal("1545.00")),
        ("1999-02", Decimal("0"), Decimal("-30.00"), Decimal("30.00")),
    ]


def test_spend_by_category_nets_refunds_and_keeps_uncategorized(db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    rows = db_conn.execute(
        "select category_slug, sum(spend) as spend from v_spend_by_category"
        " where account_id = %s and month = '1999-01' group by category_slug order by category_slug",
        (account,),
    ).fetchall()
    assert {r["category_slug"]: r["spend"] for r in rows} == {
        "credit_card_spending": Decimal("175.00"),
        "fashion": Decimal("120.00"),
        "loan_payment": Decimal("130.00"),
        "restaurants_bars": Decimal("20.00"),
        "uncategorized": Decimal("10.00"),
    }


def test_enriched_rows_carry_spend_income_and_note(db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    db_conn.execute(
        "update transactions set note = 'jacket' where account_id = %s and amount = -200", (account,)
    )
    row = db_conn.execute(
        "select spend, income, direction, level1, note from v_transactions_enriched"
        " where account_id = %s and amount = 80",
        (account,),
    ).fetchone()
    assert (row["spend"], row["income"], row["direction"], row["level1"]) == (
        Decimal("-80.00"), Decimal("0"), "incoming", "shopping",
    )


def test_active_subscriptions_are_relative_to_the_latest_import(db_conn, make_tx):
    from datetime import date

    shop = db_conn.execute(
        "insert into merchants (name, match_key) values ('ZZTEST STREAM', 'ZZTESTSTREAM') returning id"
    ).fetchone()["id"]
    for day in (date(1999, 1, 3), date(1999, 2, 3), date(1999, 3, 3)):
        tx = make_tx("-9.99", "ZZTEST STREAM", booked_at=day)
        db_conn.execute(
            "update transactions set merchant_id = %s, is_subscription = true,"
            " category_slug = 'entertainment', tx_type = 'expense' where id = %s",
            (shop, tx),
        )
    row = db_conn.execute(
        "select cadence, typical_amount, monthly_equivalent, charges from v_subscriptions"
        " where merchant_id = %s",
        (shop,),
    ).fetchone()
    assert (row["cadence"], row["typical_amount"], row["monthly_equivalent"], row["charges"]) == (
        "monthly", Decimal("9.99"), Decimal("9.99"), 3,
    )
```

(The real ledger's latest import is newer than 1999, so this synthetic subscription is not `active`, and the test does not assert on `active`. The `active` flag itself is covered through the API in Task 14.)

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/test_views.py -m integration -v` → FAIL (`relation "v_monthly_summary" does not exist`).

- [ ] **Step 4: Write the views migration**

Create `supabase/migrations/20260925110000_slice3_views.sql`:

```sql
-- The money rules, once (docs/money-rules.md; spec 2026-09-25-slice-3-design.md section 5).
-- Every total in the dashboards and the slice 4 agent comes from v_transactions_enriched.

create view v_transactions_enriched as
select t.id, t.account_id, a.name as account_name, a.bank, t.booked_at,
       to_char(t.booked_at, 'YYYY-MM') as month, t.amount, t.currency,
       case when t.amount < 0 then 'outgoing' else 'incoming' end as direction,
       t.tx_type, t.category_slug, c.level1, t.category_source,
       t.merchant_id, m.name as merchant_name, t.merchant as bank_merchant_text,
       t.description_raw, t.bank_concept, t.note, t.is_subscription, t.needs_review,
       t.transfer_pair_id,
       case when t.tx_type = 'expense' then -t.amount else 0 end as spend,
       case when t.tx_type = 'income' then t.amount else 0 end as income
from transactions t
join accounts a on a.id = t.account_id
left join categories c on c.slug = t.category_slug
left join merchants m on m.id = t.merchant_id;

comment on view v_transactions_enriched is
  'One row per transaction. spend = money spent (refunds negative), income = real income; '
  'transfers are 0 in both. Rules: docs/money-rules.md';

create view v_monthly_summary as
select month, account_id, sum(income) as income, sum(spend) as expenses,
       sum(income) - sum(spend) as savings, count(*) as row_count
from v_transactions_enriched
group by month, account_id;

comment on view v_monthly_summary is
  'Income, expenses and savings per month and account. Savings rate = savings / income, '
  'computed after summing accounts (docs/money-rules.md)';

create view v_spend_by_category as
select month, account_id, coalesce(level1, 'uncategorized') as level1,
       coalesce(category_slug, 'uncategorized') as category_slug, merchant_id, merchant_name,
       sum(spend) as spend, count(*) as row_count
from v_transactions_enriched
where tx_type = 'expense'
group by month, account_id, 3, 4, merchant_id, merchant_name;

comment on view v_spend_by_category is
  'Spend per month, account, group, category and merchant, net of refunds (docs/money-rules.md)';

create view v_subscriptions as
with charges as (
  select merchant_id, merchant_name, booked_at, -amount as charge,
         booked_at - lag(booked_at) over (partition by merchant_id order by booked_at) as gap_days
  from v_transactions_enriched
  where is_subscription and tx_type = 'expense' and amount < 0 and merchant_id is not null
), per_merchant as (
  select merchant_id, merchant_name, count(*) as charges, max(booked_at) as last_charge,
         percentile_cont(0.5) within group (order by charge)::numeric(12, 2) as typical_amount,
         percentile_cont(0.5) within group (order by gap_days) as median_gap
  from charges
  group by merchant_id, merchant_name
), latest as (
  select max(booked_at) as latest_day from transactions
)
select merchant_id, merchant_name, charges, last_charge, typical_amount,
       case when median_gap > 200 then 'yearly' else 'monthly' end as cadence,
       case when median_gap > 200 then round(typical_amount / 12, 2) else typical_amount end
         as monthly_equivalent,
       last_charge >= latest_day - case when median_gap > 200 then 400 else 45 end as active
from per_merchant cross join latest;

comment on view v_subscriptions is
  'Flagged money-out expenses per merchant. Active = charged within 45 days (monthly) or 400 '
  'days (yearly) of the latest imported transaction, not of today';
```

- [ ] **Step 5: Apply and run**

Run (repo root): `supabase migration up`; then `uv run pytest tests/test_views.py -m integration -v` → PASS.

- [ ] **Step 6: Write `docs/money-rules.md`**

Create `docs/money-rules.md` with exactly this content:

````markdown
# Money rules

How tally ai adds up your money. These rules are the contract behind every number in the
dashboards and every answer of the chat agent. They live in one SQL view,
`v_transactions_enriched`; everything else only sums it.

## The numbers

| Number | What it is |
|---|---|
| **Income** | The sum of rows whose category is an income category |
| **Expenses** | The sum of rows whose category is an expense category. A refund subtracts |
| **Savings** | Income − expenses. Money you move to your own savings or investment accounts counts as saved |
| **Savings rate** | Savings ÷ income. It can be negative (you spent more than you earned). It is empty when there is no income |
| **Out of every total** | Transfers: between your own accounts, loan money received, and a card settlement once card statements are imported |

**The category decides the type, not the sign.** A row that has no category yet counts by
its sign (money in = income, money out = expense) until you categorize it; it shows as
"Uncategorized".

## Refunds take the category of the purchase

You buy clothes for €200 and return €80. Fashion shows **€120**, and your income does not
change. A refund of a card purchase gets expense categories to choose from, and a shop's
default category applies to its refunds too. The category `refunds` is only for money back
with no purchase behind it, such as cashback or a bank bonus, and it counts as income.

If the refund lands in a later month than the purchase, that later month shows the category
as negative. That is honest: the money came back that month.

## A loan is not income

Money a bank lends you is a **liability**: you pay it back. It goes to `loan_received`, a
transfer, and never counts as income. The monthly instalments are an expense
(`loan_payment`). The bank line does not split principal from interest, so neither do we.

Example: you borrow €1,500 in January and buy a laptop with it, then repay €130 a month.
January shows negative savings (you spent €1,500 more than you earned, with borrowed money),
and each later month shows the €130 instalment as spending.

Each loan is a merchant named after its contract (`Loan ····1234`). You can rename it, and
its disbursement and instalments stay together.

## Credit cards without card statements

Only your bank accounts are imported, not the card's own statements. The card's monthly
settlement is therefore the only trace of what you bought with the card. It counts as an
expense in its own group, **Credit card**, whose detail is unknown, just like a cash
withdrawal. When card statements are imported (a later version), the settlement becomes a
transfer and the card's purchases carry the categories.

## Transfers and Bizum

- **Transfers between your own accounts are neutral.** Both sides are transfers, whether or
  not the other account is imported.
- **A Bizum you receive is income; a Bizum you send is an expense.** When a friend pays you
  back their share of a dinner, you can give that Bizum the dinner's category
  (restaurants): it then subtracts, exactly like a refund.

## Comparisons

Every change is shown against the previous period of the same length: August against July,
a quarter against the quarter before. Year to date is compared with the same dates a year
earlier. When the previous period has no imported data, no change is shown. A month without
imported data is drawn as "no data", never as zero.
````

- [ ] **Step 7: Commit**

```bash
git add supabase/migrations/20260925110000_slice3_views.sql docs/money-rules.md apps/api/tests/test_views.py apps/api/tests/money_month.py
git commit -m "feat: add the money-rule views and document the rules"
```

---

### Task 10: Periods, filters and breakdown helpers

**Files:**
- Create: `apps/api/finance/dashboard/__init__.py` (empty), `periods.py`, `filters.py`, `models.py`, `breakdowns.py`
- Test: `apps/api/tests/test_periods.py` (new, unit), `apps/api/tests/test_breakdowns.py` (new, integration)

**Interfaces:**
- Produces (exact names, used by Tasks 11-14):
  - `periods.PeriodName = Literal["month", "last_3_months", "ytd", "last_12_months", "custom"]`.
  - `periods.Period(start: date, end: date)`.
  - `periods.resolve(name, anchor, month=None, start=None, end=None) -> Period`, raising `ValueError`.
  - `periods.previous(name, period) -> Period`.
  - `periods.months_between(start, end) -> list[str]`.
  - `periods.month_end(day)`, `periods.add_months(day, n)`.
  - `periods.savings_rate(income, savings) -> float | None`.
  - `filters.Scope(accounts: tuple[UUID, ...] = (), tx_type=None, level1=None, category=None, merchant_id=None)` with `.params(period) -> dict`.
  - `filters.WHERE: str`.
  - `filters.latest_day(conn, accounts) -> date | None`.
  - `filters.has_data(conn, period, accounts) -> bool`.
  - `filters.data_months(conn, period, accounts) -> set[str]`.
  - `breakdowns.breakdown(conn, dimension: Literal["group", "category", "merchant"], value: Literal["spend", "income"], scope, period, previous: Period | None, top: int | None = 5) -> list[BreakdownRow]`.
  - `breakdowns.group_slots(conn) -> dict[str, int]`.
  - `models.*` (below).

- [ ] **Step 1: Write the failing unit tests**

Create `apps/api/tests/test_periods.py`:

```python
from datetime import date
from decimal import Decimal

import pytest

from finance.dashboard.periods import Period, months_between, previous, resolve, savings_rate

AUG_20 = date(2026, 8, 20)


@pytest.mark.parametrize(
    ("name", "expected", "before"),
    [
        ("month", (date(2026, 8, 1), date(2026, 8, 31)), (date(2026, 7, 1), date(2026, 7, 31))),
        ("last_3_months", (date(2026, 6, 1), date(2026, 8, 31)), (date(2026, 3, 1), date(2026, 5, 31))),
        ("last_12_months", (date(2025, 9, 1), date(2026, 8, 31)), (date(2024, 9, 1), date(2025, 8, 31))),
        ("ytd", (date(2026, 1, 1), date(2026, 8, 31)), (date(2025, 1, 1), date(2025, 8, 31))),
    ],
)
def test_periods_and_their_previous_period(name, expected, before):
    period = resolve(name, AUG_20)
    assert (period.start, period.end) == expected
    earlier = previous(name, period)
    assert (earlier.start, earlier.end) == before


def test_a_chosen_month_and_january_roll_back_a_year():
    period = resolve("month", AUG_20, month=date(2026, 1, 1))
    assert previous("month", period) == Period(start=date(2025, 12, 1), end=date(2025, 12, 31))


def test_a_custom_range_compares_with_the_same_number_of_days_before():
    period = resolve("custom", AUG_20, start=date(2026, 8, 10), end=date(2026, 8, 19))
    assert previous("custom", period) == Period(start=date(2026, 7, 31), end=date(2026, 8, 9))
    with pytest.raises(ValueError):
        resolve("custom", AUG_20, start=date(2026, 8, 19), end=date(2026, 8, 10))


def test_year_to_date_on_a_leap_day():
    period = Period(start=date(2028, 1, 1), end=date(2028, 2, 29))
    assert previous("ytd", period).end == date(2027, 2, 28)


def test_months_between_and_the_savings_rate():
    assert months_between(date(2025, 11, 5), date(2026, 2, 1)) == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert savings_rate(Decimal("2000"), Decimal("-300")) == -0.15
    assert savings_rate(Decimal("0"), Decimal("-30")) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_periods.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement `periods.py`**

```python
"""Periods and their comparison: the previous period of the same length (spec 2.6)."""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

PeriodName = Literal["month", "last_3_months", "ytd", "last_12_months", "custom"]


class Period(BaseModel):
    start: date
    end: date  # inclusive


def month_end(day: date) -> date:
    return day.replace(day=monthrange(day.year, day.month)[1])


def add_months(day: date, months: int) -> date:
    """The first day of the month `months` away from `day`'s month."""
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def resolve(
    name: PeriodName,
    anchor: date,
    month: date | None = None,
    start: date | None = None,
    end: date | None = None,
) -> Period:
    """`anchor` is the latest day with data (statements arrive in batches); `month` is the
    first day of a chosen calendar month."""
    if name == "custom":
        if start is None or end is None or start > end:
            raise ValueError("a custom period needs start and end, with start <= end")
        return Period(start=start, end=end)
    last = month or anchor.replace(day=1)
    if name == "month":
        return Period(start=last, end=month_end(last))
    if name == "ytd":
        return Period(start=date(last.year, 1, 1), end=month_end(last))
    count = 3 if name == "last_3_months" else 12
    return Period(start=add_months(last, 1 - count), end=month_end(last))


def _year_back(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:  # 29 February
        return day.replace(year=day.year - 1, day=28)


def previous(name: PeriodName, period: Period) -> Period:
    """August -> July, a quarter -> the quarter before, year to date -> the same dates a year
    earlier, a custom range -> the same number of days just before it."""
    if name == "ytd":
        return Period(start=_year_back(period.start), end=_year_back(period.end))
    if period.start.day == 1 and period.end == month_end(period.end):
        count = len(months_between(period.start, period.end))
        return Period(
            start=add_months(period.start, -count), end=month_end(add_months(period.start, -1))
        )
    days = (period.end - period.start).days + 1
    return Period(start=period.start - timedelta(days=days), end=period.start - timedelta(days=1))


def months_between(start: date, end: date) -> list[str]:
    out, cursor = [], start.replace(day=1)
    while cursor <= end:
        out.append(f"{cursor:%Y-%m}")
        cursor = add_months(cursor, 1)
    return out


def savings_rate(income: Decimal, savings: Decimal) -> float | None:
    """Savings ÷ income; empty without income; negative when spending beats income."""
    return None if income <= 0 else round(float(savings / income), 4)
```

Run: `uv run pytest tests/test_periods.py -v` → PASS.

- [ ] **Step 4: Implement `filters.py` and `models.py`**

`filters.py`:

```python
"""The filters every dashboard read shares, as one SQL fragment over v_transactions_enriched."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from psycopg import Connection

from finance.dashboard.periods import Period

WHERE = """
booked_at between %(start)s and %(end)s
and (cardinality(%(accounts)s::uuid[]) = 0 or account_id = any(%(accounts)s))
and (%(tx_type)s::text is null or tx_type = %(tx_type)s)
and (%(level1)s::text is null or coalesce(level1, 'uncategorized') = %(level1)s)
and (%(category)s::text is null or coalesce(category_slug, 'uncategorized') = %(category)s)
and (%(merchant_id)s::uuid is null or merchant_id = %(merchant_id)s)
"""

_ACCOUNTS = "(cardinality(%(accounts)s::uuid[]) = 0 or account_id = any(%(accounts)s))"


@dataclass(frozen=True)
class Scope:
    accounts: tuple[UUID, ...] = ()
    tx_type: str | None = None
    level1: str | None = None
    category: str | None = None
    merchant_id: UUID | None = None

    def params(self, period: Period) -> dict:
        return {
            "start": period.start,
            "end": period.end,
            "accounts": list(self.accounts),
            "tx_type": self.tx_type,
            "level1": self.level1,
            "category": self.category,
            "merchant_id": self.merchant_id,
        }


def latest_day(conn: Connection, accounts: tuple[UUID, ...]) -> date | None:
    row = conn.execute(
        f"select max(booked_at) as day from transactions where {_ACCOUNTS}",
        {"accounts": list(accounts)},
    ).fetchone()
    return row["day"]


def data_months(conn: Connection, period: Period, accounts: tuple[UUID, ...]) -> set[str]:
    """Months with at least one imported transaction of these accounts (spec 2.6)."""
    rows = conn.execute(
        "select distinct to_char(booked_at, 'YYYY-MM') as month from transactions"
        f" where booked_at between %(start)s and %(end)s and {_ACCOUNTS}",
        {"start": period.start, "end": period.end, "accounts": list(accounts)},
    ).fetchall()
    return {row["month"] for row in rows}


def has_data(conn: Connection, period: Period, accounts: tuple[UUID, ...]) -> bool:
    return bool(data_months(conn, period, accounts))
```

`models.py`:

```python
"""Response models of the dashboard, spending and transactions APIs (spec 6)."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from finance.dashboard.periods import PeriodName


class PeriodOut(BaseModel):
    name: PeriodName
    start: date
    end: date
    previous_start: date
    previous_end: date
    has_previous: bool
    latest_day: date | None


class Totals(BaseModel):
    income: Decimal
    expenses: Decimal
    savings: Decimal
    savings_rate: float | None


class CumulativePoint(BaseModel):
    day: int  # 1 = the period's first day
    date: date
    total: Decimal


class Cumulative(BaseModel):
    current: list[CumulativePoint]
    previous: list[CumulativePoint] | None


class MonthPoint(BaseModel):
    month: str  # YYYY-MM
    has_data: bool
    income: Decimal | None
    expenses: Decimal | None
    savings: Decimal | None


class BreakdownRow(BaseModel):
    key: str  # a level1 or category slug, a merchant id, "category:<slug>" or "other"
    label: str | None  # merchant name; the web labels slugs
    level1: str | None
    category_slug: str | None
    merchant_id: UUID | None
    amount: Decimal
    share: float
    previous: Decimal | None  # None when the previous period has no data; 0 = "new"
    count: int
    folded: int = 0  # entries folded into "other"


class SubscriptionOut(BaseModel):
    merchant_id: UUID
    merchant_name: str
    cadence: Literal["monthly", "yearly"]
    typical_amount: Decimal
    monthly_equivalent: Decimal
    last_charge: date
    charges: int


class Subscriptions(BaseModel):
    items: list[SubscriptionOut]
    monthly_total: Decimal
    yearly_total: Decimal


class SubscriptionsSummary(BaseModel):
    count: int
    monthly_total: Decimal
    yearly_total: Decimal


class Overview(BaseModel):
    period: PeriodOut
    kpis: Totals
    previous_kpis: Totals | None
    cumulative: Cumulative
    months: list[MonthPoint]
    by_group: list[BreakdownRow]
    by_category: list[BreakdownRow]
    by_merchant: list[BreakdownRow]
    group_slots: dict[str, int]  # level1 -> colour slot 1..5 by all-time spend
    subscriptions: SubscriptionsSummary


class Transaction(BaseModel):
    id: UUID
    booked_at: date
    account_id: UUID
    account_name: str
    amount: Decimal
    description_raw: str
    bank_merchant_text: str | None
    merchant_id: UUID | None
    merchant_name: str | None
    tx_type: str
    category_slug: str | None
    level1: str | None
    category_source: str
    is_subscription: bool
    needs_review: bool
    note: str | None
    transfer_pair_id: UUID | None


class TransactionPage(BaseModel):
    period: PeriodOut
    items: list[Transaction]
    next_cursor: str | None
    count: int
    money_in: Decimal
    money_out: Decimal


class ScopeMonth(BaseModel):
    month: str
    has_data: bool
    total: Decimal | None
    by_child: dict[str, Decimal]  # child key (or "other") -> amount; empty without children


class SpendingDetail(BaseModel):
    period: PeriodOut
    type: Literal["expense", "income"]
    level1: str | None
    category: str | None
    merchant_id: UUID | None
    merchant_name: str | None
    total: Decimal
    previous_total: Decimal | None
    count: int
    months: list[ScopeMonth]
    child_keys: list[str]  # the stacked-bar series, largest first ("other" last)
    children: list[BreakdownRow]
    top_merchants: list[BreakdownRow]
    cumulative: Cumulative
    latest: list[Transaction]
```

- [ ] **Step 5: Write the failing breakdown tests**

Create `apps/api/tests/test_breakdowns.py`:

```python
from datetime import date
from decimal import Decimal

import pytest

from finance.dashboard.breakdowns import breakdown, group_slots
from finance.dashboard.filters import Scope
from finance.dashboard.periods import Period
from tests.money_month import money_month

pytestmark = pytest.mark.integration

JAN = Period(start=date(1999, 1, 1), end=date(1999, 1, 31))
FEB = Period(start=date(1999, 2, 1), end=date(1999, 2, 28))


def test_groups_top_five_and_other(db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    rows = breakdown(db_conn, "group", "spend", Scope(accounts=(account,), tx_type="expense"), JAN, None)
    by_key = {r.key: r for r in rows}
    assert by_key["credit_card"].amount == Decimal("175.00")
    assert by_key["shopping"].amount == Decimal("120.00")
    assert sum(r.amount for r in rows) == Decimal("455.00")
    assert all(r.previous is None for r in rows)
    assert len(rows) <= 6


def test_a_negative_group_is_kept_and_sorted_last(db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    rows = breakdown(db_conn, "group", "spend", Scope(accounts=(account,), tx_type="expense"), FEB, JAN)
    assert [(r.key, r.amount) for r in rows] == [("shopping", Decimal("-30.00"))]
    assert rows[0].share == 0.0  # no positive total to divide by
    assert rows[0].previous == Decimal("120.00")


def test_merchants_without_a_merchant_fall_back_to_their_category(db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    rows = breakdown(db_conn, "merchant", "spend", Scope(accounts=(account,), tx_type="expense"), JAN, None, top=None)
    assert "category:credit_card_spending" in {r.key for r in rows}


def test_group_slots_rank_all_time_spend(db_conn):
    slots = group_slots(db_conn)
    assert sorted(slots.values()) == list(range(1, len(slots) + 1)) and len(slots) <= 5
```

- [ ] **Step 6: Implement `breakdowns.py`**

```python
"""Where the money went: by group, category or merchant, top N plus "other" (spec 7.1)."""

from decimal import Decimal
from typing import Literal

from psycopg import Connection

from finance.dashboard.filters import WHERE, Scope
from finance.dashboard.models import BreakdownRow
from finance.dashboard.periods import Period

Dimension = Literal["group", "category", "merchant"]
Value = Literal["spend", "income"]

KEYS: dict[str, str] = {
    "group": "coalesce(level1, 'uncategorized')",
    "category": "coalesce(category_slug, 'uncategorized')",
    "merchant": "coalesce(merchant_id::text, 'category:' || coalesce(category_slug, 'uncategorized'))",
}


def _query(dimension: Dimension, value: Value) -> str:
    # Both names come from the fixed dictionaries above, never from a request.
    return f"""
select {KEYS[dimension]} as key, max(merchant_name) as label, max(level1) as level1,
       max(category_slug) as category_slug, max(merchant_id::text) as merchant_id,
       sum({value}) as amount, count(*) as n
from v_transactions_enriched where {WHERE}
group by 1
"""


def _share(amount: Decimal, total: Decimal) -> float:
    return 0.0 if total <= 0 else round(float(amount / total), 4)


def breakdown(
    conn: Connection,
    dimension: Dimension,
    value: Value,
    scope: Scope,
    period: Period,
    previous: Period | None,
    top: int | None = 5,
) -> list[BreakdownRow]:
    """Sorted by amount, largest first; a negative entry (refunds only) sorts last. `previous`
    is None when the previous period has no data, so no delta is shown."""
    rows = conn.execute(_query(dimension, value), scope.params(period)).fetchall()
    before = (
        {r["key"]: r["amount"] for r in conn.execute(_query(dimension, value), scope.params(previous)).fetchall()}
        if previous
        else {}
    )
    total = sum((r["amount"] for r in rows), Decimal(0))
    out = [
        BreakdownRow(
            key=r["key"],
            label=r["label"] if dimension == "merchant" else None,
            level1=r["level1"] or ("uncategorized" if dimension == "group" else None),
            category_slug=r["category_slug"] if dimension != "group" else None,
            merchant_id=r["merchant_id"] if dimension == "merchant" else None,
            amount=r["amount"],
            share=_share(r["amount"], total),
            previous=before.get(r["key"], Decimal(0)) if previous else None,
            count=r["n"],
        )
        for r in rows
    ]
    out.sort(key=lambda row: (-row.amount, row.key))
    if top is None or len(out) <= top + 1:
        return out
    head, tail = out[:top], out[top:]
    amount = sum((row.amount for row in tail), Decimal(0))
    other_previous = (
        sum(before.values(), Decimal(0)) - sum((before.get(h.key, Decimal(0)) for h in head), Decimal(0))
        if previous
        else None
    )
    head.append(
        BreakdownRow(
            key="other", label=None, level1=None, category_slug=None, merchant_id=None,
            amount=amount, share=_share(amount, total), previous=other_previous,
            count=sum(row.count for row in tail), folded=len(tail),
        )
    )
    return head


def group_slots(conn: Connection) -> dict[str, int]:
    """Colour slots 1..5 for the groups with the most all-time spend: a period filter never
    repaints them (spec 7.2)."""
    rows = conn.execute(
        "select level1 from v_transactions_enriched where tx_type = 'expense' and level1 is not null"
        " group by level1 order by sum(spend) desc, level1 limit 5"
    ).fetchall()
    return {row["level1"]: slot for slot, row in enumerate(rows, start=1)}
```

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/test_periods.py -v` and `uv run pytest tests/test_breakdowns.py -m integration -v` → PASS. Run `uv run task lint`.

- [ ] **Step 8: Commit**

```bash
git add apps/api/finance/dashboard apps/api/tests/test_periods.py apps/api/tests/test_breakdowns.py
git commit -m "feat: add periods, shared filters, response models and breakdowns for the dashboards"
```

---

### Task 11: `GET /dashboard/overview`

**Files:**
- Create: `apps/api/finance/dashboard/totals.py`, `apps/api/finance/dashboard/subscriptions.py`, `apps/api/finance/api/periods.py`, `apps/api/finance/api/dashboard.py`
- Modify: `apps/api/finance/api/main.py`
- Test: `apps/api/tests/test_dashboard_api.py` (new, integration)

**Interfaces:**
- Consumes: Task 10 modules.
- Produces:
  - `totals.totals(conn, scope, period) -> Totals`.
  - `totals.month_series(conn, scope, end: date, count=12) -> list[MonthPoint]`.
  - `totals.cumulative(conn, scope, period, value, until: date | None = None) -> list[CumulativePoint]`.
  - `subscriptions.active_subscriptions(conn) -> Subscriptions`.
  - `api.periods.PeriodQuery` (dependency).
  - `api.periods.resolve_request(conn, query) -> Resolved(current, previous, out)`.
  - `GET /dashboard/overview?period=&month=&start=&end=&account_id=` → `Overview`.
  - `GET /dashboard/subscriptions` → `Subscriptions`.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_dashboard_api.py`:

```python
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from finance.api.deps import db
from finance.api.main import app
from tests.money_month import money_month

pytestmark = pytest.mark.integration


@pytest.fixture
def client(db_conn):
    app.dependency_overrides[db] = lambda: db_conn
    yield TestClient(app)
    app.dependency_overrides.pop(db, None)


def _overview(client, account, **params):
    return client.get("/dashboard/overview", params={"account_id": str(account), **params}).json()


def test_overview_kpis_and_breakdowns_follow_the_money_rules(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    body = _overview(client, account, period="month", month="1999-01")
    assert body["kpis"] == {"income": "2000.00", "expenses": "455.00", "savings": "1545.00", "savings_rate": 0.7725}
    assert body["period"]["has_previous"] is False
    assert body["previous_kpis"] is None
    assert sum(Decimal(r["amount"]) for r in body["by_group"]) == Decimal("455.00")
    assert len(body["months"]) == 12 and body["months"][-1] == {
        "month": "1999-01", "has_data": True, "income": "2000.00", "expenses": "455.00", "savings": "1545.00",
    }
    assert body["months"][0]["has_data"] is False
    last = body["cumulative"]["current"][-1]
    assert (last["day"], last["total"]) == (31, "455.00")


def test_february_compares_with_january(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    body = _overview(client, account, period="month", month="1999-02")
    assert body["period"]["has_previous"] is True
    assert body["previous_kpis"]["expenses"] == "455.00"
    assert body["kpis"]["savings_rate"] is None  # no income in February
    assert body["cumulative"]["previous"][-1]["total"] == "455.00"


def test_an_account_without_rows_returns_an_empty_overview(client):
    body = _overview(client, uuid4())
    assert body["kpis"]["expenses"] == "0" and body["period"]["has_previous"] is False
    assert all(not m["has_data"] for m in body["months"])
    assert body["by_group"] == []


def test_a_bad_custom_range_is_422(client):
    response = client.get("/dashboard/overview", params={"period": "custom", "start": "1999-02-01", "end": "1999-01-01"})
    assert response.status_code == 422


def test_subscriptions_endpoint_returns_totals(client):
    body = client.get("/dashboard/subscriptions").json()
    assert Decimal(body["yearly_total"]) == Decimal(body["monthly_total"]) * 12
```

`savings_rate` is `round(1545/2000, 4)`, which is `0.7725`. Decimal JSON serialization follows Pydantic v2, which writes Decimals as strings. If a total over zero rows comes back as `"0.00"` instead of `"0"`, adjust the assertion to compare `Decimal(...) == 0`. Do the same check in the other tests before changing code.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_dashboard_api.py -m integration -v` → FAIL (404 route).

- [ ] **Step 3: Implement `totals.py`**

```python
"""KPIs, the 12-month series and cumulative daily sums over v_transactions_enriched."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from psycopg import Connection

from finance.dashboard.filters import WHERE, Scope, data_months
from finance.dashboard.models import CumulativePoint, MonthPoint, Totals
from finance.dashboard.periods import Period, add_months, month_end, months_between, savings_rate

Value = Literal["spend", "income"]

_TOTALS = f"""
select coalesce(sum(income), 0) as income, coalesce(sum(spend), 0) as expenses
from v_transactions_enriched where {WHERE}
"""

_MONTHS = f"""
select month, sum(income) as income, sum(spend) as expenses
from v_transactions_enriched where {WHERE}
group by month
"""

_DAILY = {
    value: f"select booked_at, sum({value}) as amount from v_transactions_enriched"
    f" where {WHERE} group by booked_at"
    for value in ("spend", "income")
}


def totals(conn: Connection, scope: Scope, period: Period) -> Totals:
    row = conn.execute(_TOTALS, scope.params(period)).fetchone()
    savings = row["income"] - row["expenses"]
    return Totals(
        income=row["income"],
        expenses=row["expenses"],
        savings=savings,
        savings_rate=savings_rate(row["income"], savings),
    )


def twelve_months(end: date, count: int = 12) -> Period:
    return Period(start=add_months(end.replace(day=1), 1 - count), end=month_end(end))


def month_series(conn: Connection, scope: Scope, end: date, count: int = 12) -> list[MonthPoint]:
    """A month without imported data is `has_data = false`, never zeros (spec 2.6)."""
    period = twelve_months(end, count)
    with_data = data_months(conn, period, scope.accounts)
    found = {r["month"]: r for r in conn.execute(_MONTHS, scope.params(period)).fetchall()}
    points = []
    for month in months_between(period.start, period.end):
        if month not in with_data:
            points.append(MonthPoint(month=month, has_data=False, income=None, expenses=None, savings=None))
            continue
        row = found.get(month) or {"income": Decimal(0), "expenses": Decimal(0)}
        points.append(
            MonthPoint(
                month=month,
                has_data=True,
                income=row["income"],
                expenses=row["expenses"],
                savings=row["income"] - row["expenses"],
            )
        )
    return points


def cumulative(
    conn: Connection, scope: Scope, period: Period, value: Value, until: date | None = None
) -> list[CumulativePoint]:
    """Running total per day; the current period stops at the latest imported day."""
    daily = {r["booked_at"]: r["amount"] for r in conn.execute(_DAILY[value], scope.params(period)).fetchall()}
    last = min(period.end, until) if until else period.end
    points, total, day = [], Decimal(0), period.start
    while day <= last:
        total += daily.get(day, Decimal(0))
        points.append(CumulativePoint(day=(day - period.start).days + 1, date=day, total=total))
        day += timedelta(days=1)
    return points
```

- [ ] **Step 4: Implement `subscriptions.py`**

```python
"""Active subscriptions and what they cost per month and per year (spec 6)."""

from decimal import Decimal

from psycopg import Connection

from finance.dashboard.models import SubscriptionOut, Subscriptions, SubscriptionsSummary


def active_subscriptions(conn: Connection) -> Subscriptions:
    rows = conn.execute(
        "select merchant_id, merchant_name, cadence, typical_amount, monthly_equivalent,"
        " last_charge, charges from v_subscriptions where active"
        " order by monthly_equivalent desc, merchant_name"
    ).fetchall()
    items = [SubscriptionOut.model_validate(row) for row in rows]
    monthly = sum((item.monthly_equivalent for item in items), Decimal(0))
    return Subscriptions(items=items, monthly_total=monthly, yearly_total=monthly * 12)


def summary(subscriptions: Subscriptions) -> SubscriptionsSummary:
    return SubscriptionsSummary(
        count=len(subscriptions.items),
        monthly_total=subscriptions.monthly_total,
        yearly_total=subscriptions.yearly_total,
    )
```

- [ ] **Step 5: Implement `api/periods.py`**

```python
"""The period query parameters every dashboard read takes (spec 2.6, 6)."""

from dataclasses import dataclass
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query
from psycopg import Connection

from finance.dashboard.filters import has_data, latest_day
from finance.dashboard.models import PeriodOut
from finance.dashboard.periods import Period, PeriodName, previous, resolve


@dataclass(frozen=True)
class PeriodRequest:
    name: PeriodName
    month: date | None
    start: date | None
    end: date | None
    accounts: tuple[UUID, ...]


def period_request(
    period: PeriodName = "month",
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    start: date | None = None,
    end: date | None = None,
    account_id: list[UUID] = Query(default=[]),
) -> PeriodRequest:
    first = date.fromisoformat(f"{month}-01") if month else None
    return PeriodRequest(period, first, start, end, tuple(account_id))


PeriodQuery = Annotated[PeriodRequest, Depends(period_request)]


@dataclass(frozen=True)
class Resolved:
    current: Period
    previous: Period
    out: PeriodOut

    @property
    def comparable(self) -> Period | None:
        """The previous period when it has data; otherwise no delta is shown."""
        return self.previous if self.out.has_previous else None


def resolve_request(conn: Connection, request: PeriodRequest) -> Resolved:
    latest = latest_day(conn, request.accounts)
    try:
        current = resolve(request.name, latest or date.today(), request.month, request.start, request.end)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    before = previous(request.name, current)
    out = PeriodOut(
        name=request.name,
        start=current.start,
        end=current.end,
        previous_start=before.start,
        previous_end=before.end,
        has_previous=has_data(conn, before, request.accounts),
        latest_day=latest,
    )
    return Resolved(current, before, out)
```

- [ ] **Step 6: Implement `api/dashboard.py` and register it**

```python
"""The overview and the subscriptions page (spec 6, 7.1)."""

from dataclasses import replace

from fastapi import APIRouter

from finance.api.deps import Db
from finance.api.periods import PeriodQuery, resolve_request
from finance.dashboard.breakdowns import breakdown, group_slots
from finance.dashboard.filters import Scope
from finance.dashboard.models import Cumulative, Overview, Subscriptions
from finance.dashboard.subscriptions import active_subscriptions, summary
from finance.dashboard.totals import cumulative, month_series, totals

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
def overview(conn: Db, query: PeriodQuery) -> Overview:
    resolved = resolve_request(conn, query)
    scope = Scope(accounts=query.accounts)
    spend = replace(scope, tx_type="expense")
    before = resolved.comparable
    return Overview(
        period=resolved.out,
        kpis=totals(conn, scope, resolved.current),
        previous_kpis=totals(conn, scope, before) if before else None,
        cumulative=Cumulative(
            current=cumulative(conn, spend, resolved.current, "spend", until=resolved.out.latest_day),
            previous=cumulative(conn, spend, before, "spend") if before else None,
        ),
        months=month_series(conn, scope, resolved.current.end),
        by_group=breakdown(conn, "group", "spend", spend, resolved.current, before),
        by_category=breakdown(conn, "category", "spend", spend, resolved.current, before),
        by_merchant=breakdown(conn, "merchant", "spend", spend, resolved.current, before),
        group_slots=group_slots(conn),
        subscriptions=summary(active_subscriptions(conn)),
    )


@router.get("/subscriptions")
def subscriptions(conn: Db) -> Subscriptions:
    return active_subscriptions(conn)
```

In `main.py`, import `dashboard` and add `app.include_router(dashboard.router)`.

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/test_dashboard_api.py -m integration -v` → PASS. Run `uv run task test` and `uv run task lint`.

- [ ] **Step 8: Commit**

```bash
git add apps/api/finance/dashboard apps/api/finance/api apps/api/tests/test_dashboard_api.py
git commit -m "feat: serve the overview and the subscriptions list"
```

---

### Task 12: The transactions explorer API

**Files:**
- Create: `apps/api/finance/dashboard/transactions.py`
- Modify: `apps/api/finance/api/transactions.py`, `apps/api/tests/test_api.py`
- Modify: `apps/web/src/app/transactions/page.tsx`, `apps/web/src/lib/api-types.ts` (generated)
- Test: `apps/api/tests/test_transactions_api.py` (new, integration)

**Interfaces:**
- Consumes: `Scope`, `WHERE`, `Resolved` (Tasks 10-11). Task 13 reuses `page()` for its latest rows.
- Produces:
  - `TransactionFilters(scope, q=None, is_subscription=None, category_source=None, needs_review=None, saved=None)`.
  - `page(conn, filters, resolved, cursor=None, limit=100) -> TransactionPage`.
  - `GET /transactions` → `TransactionPage`. Query params: period params, `q`, `tx_type`, `level1`, `category`, `merchant_id`, `is_subscription`, `category_source`, `needs_review`, `saved=unpaired_own|refunds`, `cursor`, `limit` (1-100, default 100).

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_transactions_api.py`:

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finance.api.deps import db
from finance.api.main import app
from tests.money_month import IBAN, money_month

pytestmark = pytest.mark.integration


@pytest.fixture
def client(db_conn):
    app.dependency_overrides[db] = lambda: db_conn
    yield TestClient(app)
    app.dependency_overrides.pop(db, None)


def _list(client, account, **params):
    base = {"account_id": str(account), "period": "month", "month": "1999-01"}
    return client.get("/transactions", params={**base, **params}).json()


def test_totals_cover_the_whole_filtered_set(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    body = _list(client, account)
    assert body["count"] == 11 and len(body["items"]) == 11
    assert (body["money_in"], body["money_out"]) == ("3690.00", "895.00")


def test_search_notes_and_saved_filters(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    db_conn.execute("update transactions set note = '100% wool_coat' where account_id = %s and amount = -200", (account,))
    assert [i["note"] for i in _list(client, account, q="wool")["items"]] == ["100% wool_coat"]
    assert _list(client, account, q="100%")["count"] == 1
    assert _list(client, account, q="_")["count"] == 1  # literal underscore, not a wildcard
    assert _list(client, account, saved="unpaired_own")["count"] == 1
    assert _list(client, account, saved="refunds")["count"] == 2  # fashion and Bizum back


def test_cursor_paging_never_skips_rows_on_the_same_day(client, db_conn, make_tx):
    for n in range(5):
        make_tx(f"-{n + 1}.00", f"ZZTEST SAME DAY {n}", iban=IBAN, booked_at=date(1999, 3, 9))
    account = db_conn.execute("select id from accounts where iban = %s", (IBAN,)).fetchone()["id"]
    seen, cursor = [], None
    while True:
        params = {"month": "1999-03", "limit": 2, **({"cursor": cursor} if cursor else {})}
        body = _list(client, account, **params)
        seen += [i["id"] for i in body["items"]]
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 5


def test_card_numbers_are_masked(client, db_conn, make_tx):
    make_tx("-9.90", "PAGO CON TARJETA | 4000123412341234 ZZTEST ACME", iban=IBAN, booked_at=date(1999, 4, 1))
    account = db_conn.execute("select id from accounts where iban = %s", (IBAN,)).fetchone()["id"]
    [item] = _list(client, account, month="1999-04")["items"]
    assert item["description_raw"] == "PAGO CON TARJETA | •••• 1234 ZZTEST ACME"
```

Money in for January: 2000 + 80 + 1500 + 50 + 60 = 3690. Money out: 200 + 130 + 175 + 300 + 80 + 10 = 895.

In `apps/api/tests/test_api.py`, delete `_Rows` and `test_transactions_mask_card_numbers` (moved to the integration test above). Keep `test_transactions_rejects_malformed_month` and `test_openapi_exposes_web_schemas` (`Transaction` is still a schema name); add `"TransactionPage"` to the latter's set.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_transactions_api.py -m integration -v` → FAIL.

- [ ] **Step 3: Implement `dashboard/transactions.py`**

```python
"""The explorer: filters, search, cursor paging and totals over the whole filtered set."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from psycopg import Connection

from finance.dashboard.filters import WHERE, Scope
from finance.dashboard.models import Transaction, TransactionPage
from finance.ingestion.structure import mask_card_numbers

Saved = Literal["unpaired_own", "refunds"]

_FILTERS = WHERE + r"""
and (%(q)s::text is null or merchant_name ilike %(pattern)s or bank_merchant_text ilike %(pattern)s
     or description_raw ilike %(pattern)s or note ilike %(pattern)s)
and (%(is_subscription)s::boolean is null or is_subscription = %(is_subscription)s)
and (%(category_source)s::text is null or category_source = %(category_source)s)
and (%(needs_review)s::boolean is null or needs_review = %(needs_review)s)
and (%(saved)s::text is null
     or (%(saved)s = 'unpaired_own' and category_slug = 'own_accounts' and transfer_pair_id is null)
     or (%(saved)s = 'refunds' and tx_type = 'expense' and amount > 0))
"""

_PAGE = f"""
select id, booked_at, account_id, account_name, amount, description_raw, bank_merchant_text,
       merchant_id, merchant_name, tx_type, category_slug, level1, category_source,
       is_subscription, needs_review, note, transfer_pair_id
from v_transactions_enriched
where {_FILTERS}
  and (%(cursor_day)s::date is null or (booked_at, id) < (%(cursor_day)s, %(cursor_id)s::uuid))
order by booked_at desc, id desc
limit %(limit)s
"""

_TOTALS = f"""
select count(*) as n,
       coalesce(sum(amount) filter (where amount > 0), 0) as money_in,
       coalesce(-sum(amount) filter (where amount < 0), 0) as money_out
from v_transactions_enriched where {_FILTERS}
"""


@dataclass(frozen=True)
class TransactionFilters:
    scope: Scope
    q: str | None = None
    is_subscription: bool | None = None
    category_source: str | None = None
    needs_review: bool | None = None
    saved: Saved | None = None


def _like(text: str) -> str:
    """Search is literal: % and _ typed by the user are not wildcards."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _cursor(value: str | None) -> tuple[date | None, UUID | None]:
    if not value:
        return None, None
    day, _, row_id = value.partition("_")
    return date.fromisoformat(day), UUID(row_id)


def page(conn: Connection, filters: TransactionFilters, resolved, cursor: str | None = None, limit: int = 100) -> TransactionPage:
    q = (filters.q or "").strip() or None
    cursor_day, cursor_id = _cursor(cursor)
    params = filters.scope.params(resolved.current) | {
        "q": q,
        "pattern": _like(q) if q else None,
        "is_subscription": filters.is_subscription,
        "category_source": filters.category_source,
        "needs_review": filters.needs_review,
        "saved": filters.saved,
        "cursor_day": cursor_day,
        "cursor_id": cursor_id,
        "limit": limit + 1,  # one extra row tells whether another page exists
    }
    rows = conn.execute(_PAGE, params).fetchall()
    more = len(rows) > limit
    rows = rows[:limit]
    items = [
        Transaction.model_validate(row | {"description_raw": mask_card_numbers(row["description_raw"])})
        for row in rows
    ]
    total = conn.execute(_TOTALS, params).fetchone()
    last = items[-1] if items else None
    return TransactionPage(
        period=resolved.out,
        items=items,
        next_cursor=f"{last.booked_at.isoformat()}_{last.id}" if more and last else None,
        count=total["n"],
        money_in=total["money_in"],
        money_out=total["money_out"],
    )
```

In Postgres, `ilike` uses `\` as the default escape character, so the escaped pattern matches literally.

- [ ] **Step 4: Replace the list route in `api/transactions.py`**

```python
from finance.api.periods import PeriodQuery, resolve_request
from finance.categorization.models import CategorySource
from finance.dashboard.filters import Scope
from finance.dashboard.models import Transaction, TransactionPage  # noqa: F401  (schema name)
from finance.dashboard.transactions import Saved, TransactionFilters, page


@router.get("")
def list_transactions(
    conn: Db,
    query: PeriodQuery,
    q: str | None = Query(default=None, max_length=100),
    tx_type: Literal["expense", "income", "transfer"] | None = None,
    level1: str | None = None,
    category: str | None = None,
    merchant_id: UUID | None = None,
    is_subscription: bool | None = None,
    category_source: CategorySource | None = None,
    needs_review: bool | None = None,
    saved: Saved | None = None,
    cursor: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}_[0-9a-f-]{36}$"),
    limit: int = Query(default=100, ge=1, le=100),
) -> TransactionPage:
    resolved = resolve_request(conn, query)
    scope = Scope(accounts=query.accounts, tx_type=tx_type, level1=level1, category=category, merchant_id=merchant_id)
    filters = TransactionFilters(scope, q, is_subscription, category_source, needs_review, saved)
    return page(conn, filters, resolved, cursor, limit)
```

Delete the old `_SELECT` and the old `Transaction` class (the model now lives in `dashboard/models.py`). Add `from typing import Literal`.

- [ ] **Step 5: Run the API tests**

Run: `uv run pytest tests/test_transactions_api.py tests/test_api.py -m "integration or not integration" -v` → PASS.

- [ ] **Step 6: Keep the current web page working**

Start the API (`uv run task api`), then from `apps/web` run `npm run gen:api`. In `apps/web/src/app/transactions/page.tsx`:
- replace the fetch with `const page = await apiGet<Schemas["TransactionPage"]>(`/transactions?${query}`);`;
- build `query` from `{ period: "month", ...(month ? { month } : {}) }`;
- iterate `page.items`;
- show `tx.merchant_name ?? tx.bank_merchant_text ?? tx.description_raw` in the description cell;
- replace the `LIMIT` hint with `{page.next_cursor && <p ...>Showing the latest 100 transactions of {page.count}.</p>}`.

This page is replaced in slice 3b; the change only keeps it working. Run `npm run lint && npm run build` → PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/finance apps/api/tests apps/web/src
git commit -m "feat: add the transactions explorer API with search, filters and cursor paging"
```

---

### Task 13: `GET /spending/detail`

**Files:**
- Create: `apps/api/finance/api/spending.py`
- Modify: `apps/api/finance/dashboard/totals.py` (add `scope_months`), `apps/api/finance/api/main.py`
- Test: `apps/api/tests/test_spending_api.py` (new, integration)

**Interfaces:**
- Consumes: Tasks 10, 11, and `transactions.page` from Task 12.
- Produces:
  - `totals.scope_months(conn, scope, value, end, child: Dimension | None, child_keys: list[str]) -> list[ScopeMonth]`.
  - `GET /spending/detail?type=expense|income&level1=&category=&merchant_id=` + period params → `SpendingDetail`.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_spending_api.py`:

```python
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from finance.api.deps import db
from finance.api.main import app
from tests.money_month import money_month

pytestmark = pytest.mark.integration


@pytest.fixture
def client(db_conn):
    app.dependency_overrides[db] = lambda: db_conn
    yield TestClient(app)
    app.dependency_overrides.pop(db, None)


def _detail(client, account, **params):
    base = {"account_id": str(account), "period": "month", "month": "1999-01"}
    return client.get("/spending/detail", params={**base, **params}).json()


def test_a_group_page_lists_its_categories_and_months(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    body = _detail(client, account, level1="shopping")
    assert body["total"] == "120.00" and body["count"] == 2
    assert [c["key"] for c in body["children"]] == ["fashion"]
    assert body["child_keys"] == ["fashion"]
    january = body["months"][-1]
    assert january == {"month": "1999-01", "has_data": True, "total": "120.00", "by_child": {"fashion": "120.00"}}
    assert len(body["latest"]) == 2


def test_a_category_page_lists_merchants_and_income_works_the_same(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    category = _detail(client, account, level1="shopping", category="fashion")
    assert category["children"][0]["key"].startswith("category:") or category["children"][0]["merchant_id"]
    income = _detail(client, account, type="income")
    assert income["total"] == "2000.00" and [c["key"] for c in income["children"]] == ["salary"]


def test_february_shows_a_negative_total_against_january(client, db_conn, make_tx):
    account = money_month(db_conn, make_tx)
    body = _detail(client, account, level1="shopping", month="1999-02")
    assert (body["total"], body["previous_total"]) == ("-30.00", "120.00")
    assert body["cumulative"]["current"][-1]["total"] == "-30.00"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_spending_api.py -m integration -v` → FAIL (404).

- [ ] **Step 3: Implement `scope_months` in `totals.py`**

```python
from finance.dashboard.breakdowns import KEYS, Dimension


def scope_months(
    conn: Connection,
    scope: Scope,
    value: Value,
    end: date,
    child: Dimension | None,
    child_keys: list[str],
) -> list[ScopeMonth]:
    """12 months of one scope, split by its children for the stacked bars: `child_keys` in
    order, the rest summed as "other" (spec 7.2)."""
    period = twelve_months(end)
    with_data = data_months(conn, period, scope.accounts)
    key = KEYS[child] if child else "'total'"
    rows = conn.execute(
        f"select month, {key} as key, sum({value}) as amount from v_transactions_enriched"
        f" where {WHERE} group by 1, 2",
        scope.params(period),
    ).fetchall()
    by_month: dict[str, dict[str, Decimal]] = {}
    for row in rows:
        bucket = row["key"] if not child or row["key"] in child_keys else "other"
        month = by_month.setdefault(row["month"], {})
        month[bucket] = month.get(bucket, Decimal(0)) + row["amount"]
    points = []
    for month in months_between(period.start, period.end):
        parts = by_month.get(month, {})
        if month not in with_data:
            points.append(ScopeMonth(month=month, has_data=False, total=None, by_child={}))
            continue
        total = sum(parts.values(), Decimal(0))
        points.append(ScopeMonth(month=month, has_data=True, total=total, by_child=parts if child else {}))
    return points
```

Add `ScopeMonth` to the models import.

- [ ] **Step 4: Implement `api/spending.py`**

```python
"""One scope's page: a group, a category, a merchant, or income (spec 6, 7.1)."""

from dataclasses import replace
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter

from finance.api.deps import Db
from finance.api.periods import PeriodQuery, resolve_request
from finance.dashboard.breakdowns import breakdown
from finance.dashboard.filters import Scope
from finance.dashboard.models import Cumulative, SpendingDetail
from finance.dashboard.totals import cumulative, scope_months, totals
from finance.dashboard.transactions import TransactionFilters, page

router = APIRouter(prefix="/spending", tags=["spending"])


@router.get("/detail")
def detail(
    conn: Db,
    query: PeriodQuery,
    type: Literal["expense", "income"] = "expense",
    level1: str | None = None,
    category: str | None = None,
    merchant_id: UUID | None = None,
) -> SpendingDetail:
    resolved = resolve_request(conn, query)
    before = resolved.comparable
    scope = Scope(accounts=query.accounts, tx_type=type, level1=level1, category=category, merchant_id=merchant_id)
    value = "spend" if type == "expense" else "income"
    child = None if merchant_id else ("merchant" if category else "category")
    now = totals(conn, scope, resolved.current)
    amount = now.expenses if type == "expense" else now.income
    previous_total = None
    if before:
        then = totals(conn, scope, before)
        previous_total = then.expenses if type == "expense" else then.income
    children = (
        breakdown(conn, child, value, scope, resolved.current, before, top=None if child == "category" else 10)
        if child
        else []
    )
    keys = [c.key for c in children if c.key != "other"][:5]
    if len(children) > len(keys):
        keys.append("other")
    listing = page(conn, TransactionFilters(scope=scope), resolved, limit=5)
    name = None
    if merchant_id:
        row = conn.execute("select name from merchants where id = %s", (merchant_id,)).fetchone()
        name = row["name"] if row else None
    return SpendingDetail(
        period=resolved.out,
        type=type,
        level1=level1,
        category=category,
        merchant_id=merchant_id,
        merchant_name=name,
        total=amount,
        previous_total=previous_total,
        count=listing.count,
        months=scope_months(conn, scope, value, resolved.current.end, child, keys),
        child_keys=keys,
        children=children,
        top_merchants=breakdown(conn, "merchant", value, scope, resolved.current, before)
        if child == "category"
        else [],
        cumulative=Cumulative(
            current=cumulative(conn, scope, resolved.current, value, until=resolved.out.latest_day),
            previous=cumulative(conn, scope, before, value) if before else None,
        ),
        latest=listing.items,
    )
```

Register the router in `main.py`. Drop the unused imports (`replace`, `Decimal`) if `ruff` flags them.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_spending_api.py -m integration -v` → PASS. Run `uv run task lint`.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance apps/api/tests/test_spending_api.py
git commit -m "feat: serve group, category, merchant and income detail pages"
```

---

### Task 14: Trusted hosts and the subscriptions `active` flag

**Files:**
- Modify: `apps/api/finance/settings.py`, `apps/api/finance/api/main.py`, `.env.example`
- Test: `apps/api/tests/test_api.py`, `apps/api/tests/test_dashboard_api.py`

**Interfaces:**
- Produces: `Settings.trusted_hosts: list[str]` (default `["localhost", "127.0.0.1", "testserver"]`); requests with another `Host` get 400.

- [ ] **Step 1: Write the failing tests**

Append to `apps/api/tests/test_api.py`:

```python
def test_a_request_for_another_host_is_refused():
    response = client.get("/health", headers={"host": "attacker.example"})
    assert response.status_code == 400
    assert client.get("/health").status_code == 200
```

Append to `apps/api/tests/test_dashboard_api.py`:

```python
def test_a_subscription_is_active_relative_to_the_latest_import(client, db_conn, make_tx):
    from datetime import date

    latest = db_conn.execute("select max(booked_at) as d from transactions").fetchone()["d"]
    shop = db_conn.execute(
        "insert into merchants (name, match_key) values ('ZZTEST STREAM', 'ZZTESTSTREAM') returning id"
    ).fetchone()["id"]
    for day in (latest.replace(day=1), latest):
        tx = make_tx("-9.99", "ZZTEST STREAM", booked_at=day)
        db_conn.execute(
            "update transactions set merchant_id = %s, is_subscription = true,"
            " category_slug = 'entertainment', tx_type = 'expense' where id = %s",
            (shop, tx),
        )
    names = [s["merchant_name"] for s in client.get("/dashboard/subscriptions").json()["items"]]
    assert "ZZTEST STREAM" in names
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_api.py -k another_host -v` → FAIL (200).

- [ ] **Step 3: Implement**

`settings.py`: add `trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]`, with the comment `# TestClient sends Host: testserver.`

`main.py`:

```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# A DNS-rebinding page reaches the API under its own host name: refuse any other Host.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=get_settings().trusted_hosts)
```

`.env.example`: add `# TRUSTED_HOSTS=["localhost","127.0.0.1"]` under the CORS line, with a one-line comment.

- [ ] **Step 4: Run all tests**

Run: `uv run task test` and `uv run task test-integration` → PASS. Run `uv run task lint`.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance .env.example apps/api/tests
git commit -m "fix: refuse requests for other host names"
```

---

### Task 15: Documentation and project instructions

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `docs/superpowers/specs/2026-09-22-personal-finance-agent-v1-design.md` (section 16)

- [ ] **Step 1: Link the money rules**

`README.md`: in the section that describes the dashboards or categorization, add the line: `How the numbers add up (refunds, loans, credit cards, transfers): [docs/money-rules.md](docs/money-rules.md).`

`CLAUDE.md`:
- in "Commands", add `cd apps/api && uv run finance categorize --all --rules-only   # pairing and rules only, no jev spend`;
- in the restore paragraph, change "the labels, which are the golden set" to "the labels (the golden set) and your notes";
- in "What this is", add: `Money rules (what counts as income, spending, transfers): docs/money-rules.md.`

v1 spec, section 16: append

```markdown
### Slice 3 amendments (2026-09-25)

Designed in `2026-09-25-slice-3-design.md`: refunds take the purchase's category, loans and
unitemized card spending, category-driven row types, notes, the views and the dashboard API.
That document lists the v1 sections it changes (its section 13).
```

- [ ] **Step 2: Commit**

```bash
git add README.md CLAUDE.md docs/superpowers/specs/2026-09-22-personal-finance-agent-v1-design.md
git commit -m "docs: link the money rules and record the slice 3 amendments"
```

---

### Task 16: Apply the rules to the real ledger (with Raul)

This task touches Raul's real data. Do each step with him, and paste only counts in chat, never rows.

- [ ] **Step 1: Back up and migrate** (skip whatever Tasks 1 and 9 already did)

From `apps/api`: `uv run finance labels export --force` (or a new dated file). From the repo root: `supabase migration up`. From `apps/api`: `uv run finance seed`.

- [ ] **Step 2: Re-apply the rules without jev**

Run: `uv run finance categorize --all --rules-only`
Expected: a summary line with `rule=<n>`. The card settlements now read `credit_card_spending`, the loan rows `loan_received` / `loan_payment`, and loans have `Loan ····NNNN` merchants. Check with:

```sql
select category_slug, count(*) from transactions
where category_slug in ('credit_card_spending', 'loan_received', 'loan_payment', 'credit_card_payment')
group by 1;
```

Expected: `credit_card_payment` is gone (0 rows).

- [ ] **Step 3: Send the purchase refunds labelled `refunds` back to review**

List them first (counts and dates only):

```sql
select booked_at, amount from transactions
where category_slug = 'refunds' and amount > 0 and bank_concept ilike 'PAGO CON TARJETA%';
```

With Raul's approval:

```sql
update transactions set category_source = 'none', needs_review = true
where category_slug = 'refunds' and amount > 0 and bank_concept ilike 'PAGO CON TARJETA%';
```

Then, **with Raul's explicit approval of the paid run** (a handful of rows): `uv run finance categorize`. Raul labels them in `/review` with the purchase's category, and his new labels supersede the old ones in the golden set.

- [ ] **Step 4: Eval on the new taxonomy (paid, Raul approves first)**

Run: `uv run finance eval-categorization --note "slice 3 taxonomy: refunds take the purchase category, loans, unitemized card spending"`
Expected: a report plus a new line in `docs/evals/HISTORY.md`. Compare it with the previous line (L2 87.4 %, P@0.95 98.9 %). If the refund rows are misses, the report says so; do not tune criteria in this slice.

- [ ] **Step 5: Commit the eval line**

```bash
git add docs/evals/HISTORY.md
git commit -m "docs: record the first benchmark on the slice 3 taxonomy"
```

---

## Self-review notes (for the executor)

- **Order:** tasks run in number order, 1 → 16. Task 13 uses `page()` from Task 12.
- After Tasks 11-13 the web types must be regenerated before slice 3b starts.
- Spec items that live in slice 3b, not here: the web pages, pickers, side panel, `/review` fixes (the description on expanded lines, the stale item after a merge, the "run `finance categorize`" hint wording), the restyle, `agent-browser` checks and the dogfood pass.
