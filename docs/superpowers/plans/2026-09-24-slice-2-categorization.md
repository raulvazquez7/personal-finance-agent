# Slice 2: Categorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every imported transaction gets a merchant, a two-level category and a subscription flag through the cascade pairing → system rules → jev → merchant defaults → confidence gate → `/review`, and a benchmark command measures the categorizer against the user's labels.

**Architecture:** A pure, async categorizer (`finance/categorization/categorizer.py`) turns `TxInput` rows into `Categorization` results using a `Taxonomy`, system `Rule`s, an in-memory `MerchantRoster` and a `Jev` protocol; it never touches the database, so the import path and the eval dry run share it. Thin store modules load rows and persist results with plain SQL; FastAPI routes and a minimal Next.js `/review` page sit on top. Labels history (`transaction_labels`, `source = user`) is the golden set.

**Tech Stack:** Python 3.12, uv, FastAPI, psycopg 3 (dict rows, plain SQL), Pydantic v2, pydantic-settings, Typer, `typesafe-sdk` (jev), `langfuse` v4, PyYAML, pytest; Supabase Postgres migrations; Next.js 16 App Router, TypeScript, Tailwind v4, shadcn/ui `base-nova` (Base UI), `openapi-typescript`, `agent-browser` for UI checks.

**Spec:** `docs/superpowers/specs/2026-09-22-personal-finance-agent-v1-design.md` (sections 3.2, 4.2, 4.4, 5, 6, 7, 10, 11.1, 12, 13.1, 14, "Slice 2 amendments"). Evidence and the validated jev questions: `docs/superpowers/spikes/2026-09-23-jev-categorization/` (`README.md`, `run.py`).

## Global Constraints

- Everything in English: code, comments, docs, commits, UI copy.
- Simplicity: one responsibility per file, no abstraction for a single caller, libraries used as their docs show. Check `context7` for version-sensitive APIs (typesafe-sdk, langfuse v4, shadcn base combobox, Next.js 16).
- Python: `apps/api`, uv, Python 3.12, ruff line length 100, rules `E,F,I,UP,B`. Plain SQL through `finance.db.connection()` (dict rows). Pydantic models at every API boundary.
- The full card number is never stored outside `description_raw` and never sent to jev (spec 4.2).
- jev is used only for transaction categorization (spec 5.1). Deterministic code for pairing, rules, thresholds, grouping and metrics.
- Thresholds (settings, spec 5.2): category level 2 and level 1 `0.95`; new merchant brand `0.5`; merge `0.8`; merge suggestion `0.5`–`0.8`; subscription noul `> 0.7`, expenses only. jev concurrency `8`.
- Own-account pairing: same absolute amount, opposite sign, different accounts, booking dates within `2` days, neither already paired, both matching `TRASPASO|TRANSFER|BIZUM|TRF` (case-insensitive, on `description_raw`); user-labelled rows are never paired (spec 4.4).
- Langfuse on every jev call from the first implementation; eval calls carry the tag `eval`.
- No real bank data in tests, fixtures or docs: short synthetic text, fake IBANs and names. `data/raw/`, `eval-output/`, `data/labels/` and the spike `output/` stay git-ignored.
- Never run `supabase db reset` on the developer machine during this plan: apply migrations with `supabase migration up`. After Task 15, export labels first (`uv run finance labels export`).
- Integration tests are marked `integration`, need `supabase start`, the migration applied and `uv run finance seed`, and run inside a transaction that is rolled back (`db_conn` fixture, Task 5).
- Web: shadcn/ui `base-nova` (Base UI primitives), server components fetch from the API, client components only for interaction, minimal copy. Every web task ends with an `agent-browser` core check (`agent-browser skills get core`); absolute paths for `upload` and `screenshot`; named session; `close` when done. Captures go to `dogfood-output/` (git-ignored).
- Conventional commits, one per task at least, author from repo config, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Commands: `cd apps/api && uv run task test` (unit), `uv run task test-integration`, `uv run task lint`; `cd apps/web && npm run lint && npx tsc --noEmit && npm run build`.

## Review Focus

- A merchant default set for expenses meets an incoming row of the same merchant (a refund): the default must not apply; the row keeps jev's income category (test in Task 9).
- `TYPESAFE_API_KEY` missing or jev failing during an import: the import still succeeds and reports its counts; rows stay `category_source = none` and a later `finance categorize` picks them up (tests in Task 10).
- Re-running `finance categorize --all` or `POST /categorize/run?all=true`: rows labelled by the user are never overwritten and no duplicate merchant is created (tests in Task 10).
- The API is down while the web layout renders the navigation badge: every page still renders, the badge is simply hidden (code and check in Task 13).
- Two possible counterparts with the same amount for one transfer: pairing is one-to-one, nearest date first; a user-labelled row is never paired (tests in Task 5).

## Not in this plan

Dashboards and their views (`v_monthly_summary`, `v_spend_by_category`, `v_subscriptions`,
`v_transactions_enriched`), the `/subscriptions` page and `/settings` belong to slice 3 (spec 14).
The category column in `/transactions`, the recurrence detector and Langfuse Datasets are out of
scope (spec 12).

## File map

```
supabase/migrations/20260924000000_categorization.sql     Task 1  schema + card-number backfill
supabase/seed/categories.yaml                              Task 3  taxonomy with jev criteria (generated from the spike)
supabase/seed/rules.yaml                                   Task 3  system rules
apps/api/finance/ingestion/structure.py                    Task 2  bank_concept / merchant / card_last4
apps/api/finance/categorization/taxonomy.py                Task 3  Category, Taxonomy, loaders
apps/api/finance/categorization/rules.py                   Task 3-4 Rule, loaders, match_rule
apps/api/finance/categorization/seed.py                    Task 3  upsert seeds (`finance seed`)
apps/api/finance/categorization/pairing.py                 Task 5  find_pairs, pair_transfers
apps/api/finance/categorization/jev_questions.py           Task 6  fragments, match_key, question specs
apps/api/finance/categorization/jev_client.py              Task 7  Jev protocol, TypesafeJev (+ Langfuse)
apps/api/finance/tracing.py                                Task 7  Langfuse client from settings
apps/api/finance/categorization/merchants.py               Task 8  MerchantRef, MerchantRoster, resolve_merchant
apps/api/finance/categorization/models.py                  Task 8  TxInput, Categorization
apps/api/finance/categorization/categorizer.py             Task 9  decide, categorize (pure, async)
apps/api/finance/categorization/store.py                   Task 10 load/save, categorize_pending
apps/api/finance/categorization/labels.py                  Task 11 label, confirm, merge, dismiss
apps/api/finance/categorization/review_queue.py            Task 12 review items (pure)
apps/api/finance/api/{review,categories,merchants,categorize}.py  Task 12 routes
apps/web/src/app/review/*                                  Task 13 /review page
apps/api/finance/evals/{metrics,report,run}.py             Task 14 benchmark
apps/api/finance/evals/labels_io.py                        Task 15 labels export/import
docs/evals/HISTORY.md                                      Task 15 first production line
```

---

### Task 1: Migration for categorization and card-number cleanup

**Files:**
- Create: `supabase/migrations/20260924000000_categorization.sql`
- Test: `apps/api/tests/test_schema.py`

**Interfaces:**
- Produces tables `categories`, `merchants`, `rules`, `transaction_labels`; new `transactions` columns `bank_concept`, `card_last4`, `merchant_id`, `merchant_source`, `merchant_confidence`, `category_probabilities`, `subscription_score`; `category_source` accepts `merchant`; `jev_suggestions` dropped.

- [ ] **Step 1: Write the failing integration test**

```python
# apps/api/tests/test_schema.py
"""The slice-2 schema is applied and no card number survives outside description_raw."""

import pytest

from finance.db import connection

pytestmark = pytest.mark.integration


def _columns(conn, table: str) -> set[str]:
    rows = conn.execute(
        "select column_name from information_schema.columns where table_name = %s", (table,)
    ).fetchall()
    return {row["column_name"] for row in rows}


def test_categorization_tables_exist():
    with connection() as conn:
        assert {"slug", "tx_type", "level1", "what", "not_for"} <= _columns(conn, "categories")
        assert {"match_key", "confirmed", "merge_candidate_id"} <= _columns(conn, "merchants")
        assert {"match_field", "pattern", "direction"} <= _columns(conn, "rules")
        assert {"source", "model", "is_subscription"} <= _columns(conn, "transaction_labels")


def test_transactions_gain_categorization_columns():
    with connection() as conn:
        columns = _columns(conn, "transactions")
    assert {"bank_concept", "card_last4", "merchant_id", "category_probabilities"} <= columns
    assert "jev_suggestions" not in columns


def test_no_card_number_in_merchant():
    with connection() as conn:
        row = conn.execute(
            "select count(*) as n from transactions where merchant ~ '\\d{12,19}'"
        ).fetchone()
    assert row["n"] == 0
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_schema.py -m integration -v`
Expected: FAIL (`categories` has no columns; card numbers still present).

- [ ] **Step 3: Write the migration**

```sql
-- supabase/migrations/20260924000000_categorization.sql
-- Slice 2: taxonomy, merchants, system rules, label history; card numbers leave `merchant`.

create table categories (
  slug     text primary key,
  tx_type  text not null check (tx_type in ('income', 'expense', 'transfer')),
  level1   text not null,
  what     text not null,
  not_for  text
);

create table merchants (
  id                  uuid primary key default gen_random_uuid(),
  name                text not null unique,
  match_key           text not null unique,
  confirmed           boolean not null default false,
  category_slug       text references categories(slug),
  is_subscription     boolean,
  merge_candidate_id  uuid references merchants(id) on delete set null,
  merge_confidence    real,
  created_at          timestamptz not null default now()
);

create table rules (
  id             uuid primary key default gen_random_uuid(),
  name           text not null unique,
  bank           bank,
  match_field    text not null check (match_field in ('bank_concept', 'merchant')),
  pattern        text not null,
  direction      text not null check (direction in ('outgoing', 'incoming', 'any')),
  category_slug  text not null references categories(slug),
  enabled        boolean not null default true
);

alter table transactions
  add column bank_concept            text,
  add column card_last4              char(4),
  add column merchant_id             uuid references merchants(id),
  add column merchant_source         text not null default 'none'
                                     check (merchant_source in ('jev', 'user', 'none')),
  add column merchant_confidence     real,
  add column category_probabilities  jsonb,
  add column subscription_score      real,
  drop column jev_suggestions,
  add constraint transactions_category_fk foreign key (category_slug) references categories(slug);

alter table transactions drop constraint transactions_category_source_check;
alter table transactions add constraint transactions_category_source_check
  check (category_source in ('rule', 'merchant', 'jev', 'user', 'none'));

create index transactions_review_idx on transactions (needs_review) where needs_review;
create index transactions_merchant_idx on transactions (merchant_id);

create table transaction_labels (
  id               uuid primary key default gen_random_uuid(),
  transaction_id   uuid not null references transactions(id) on delete cascade,
  merchant_id      uuid references merchants(id) on delete set null,
  category_slug    text references categories(slug),
  is_subscription  boolean not null default false,
  source           text not null check (source in ('rule', 'merchant', 'jev', 'user')),
  confidence       real,
  model            text,
  labeled_at       timestamptz not null default now()
);

create index transaction_labels_tx_idx on transaction_labels (transaction_id, labeled_at desc);

-- Backfill for rows imported in slice 1 (spec 4.2).
update transactions t
set bank_concept = split_part(t.description_raw, ' | ', 1)
from accounts a
where a.id = t.account_id and a.bank = 'bbva' and t.description_raw like '% | %';

update transactions
set card_last4 = right(substring(merchant from '\d{12,19}'), 4),
    merchant = nullif(btrim(regexp_replace(regexp_replace(merchant, '\m\d{12,19}\M', '', 'g'),
                                           '\s+', ' ', 'g')), '')
where merchant ~ '\d{12,19}';
```

- [ ] **Step 4: Apply it without wiping data and run the test**

Run: `supabase migration up` (never `db reset`), then `cd apps/api && uv run pytest tests/test_schema.py -m integration -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20260924000000_categorization.sql apps/api/tests/test_schema.py
git commit -m "feat: add the categorization schema and strip card numbers from merchants"
```

### Task 2: Structure bank lines at import

**Files:**
- Create: `apps/api/finance/ingestion/structure.py`
- Modify: `apps/api/finance/ingestion/importer.py` (insert statement and `transaction_rows`)
- Test: `apps/api/tests/test_structure.py`, `apps/api/tests/test_importer.py`

**Interfaces:**
- Produces: `structure(bank: Bank, description_raw: str, merchant: str | None) -> Structured` with fields `bank_concept: str | None`, `merchant: str | None`, `card_last4: str | None`.
- Produces: `transaction_rows(...)` tuples now end with `bank_concept, card_last4` (indexes 11 and 12); index 7 holds the cleaned merchant.

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/test_structure.py
from finance.ingestion.structure import structure


def test_bbva_concept_is_split_and_card_number_removed():
    result = structure(
        "bbva",
        "PAGO CON TARJETA EN SUPERMERCADOS | 1234567812345678 SUPER ACME 0042",
        "SUPER ACME 1234567812345678 0042",
    )
    assert result.bank_concept == "PAGO CON TARJETA EN SUPERMERCADOS"
    assert result.merchant == "SUPER ACME 0042"
    assert result.card_last4 == "5678"


def test_caixabank_has_no_concept():
    result = structure("caixabank", "BIZUM ENVIADO", "BIZUM ENVIADO")
    assert result.bank_concept is None
    assert result.merchant == "BIZUM ENVIADO"
    assert result.card_last4 is None


def test_merchant_made_only_of_a_card_number_becomes_empty():
    assert structure("bbva", "X | 1234567812345678", "1234567812345678").merchant is None


def test_short_numbers_are_not_card_numbers():
    assert structure("bbva", "X | ACME 0042", "ACME 0042").merchant == "ACME 0042"
```

Add to `apps/api/tests/test_importer.py`:

```python
def test_transaction_rows_carry_concept_and_card_last4():
    header = StatementHeader(bank="bbva", iban="ES9101820418450200051332")
    card = NormalizedTransaction(
        booked_at=date(2026, 7, 3),
        amount=Decimal("-9.90"),
        description_raw="PAGO CON TARJETA EN SUPERMERCADOS | 1234567812345678 SUPER ACME",
        merchant="1234567812345678 SUPER ACME",
        balance_after=Decimal("5"),
    )
    row = transaction_rows(ParsedStatement(header=header, transactions=[card]), uuid4(), uuid4())[0]
    assert row[7] == "SUPER ACME"
    assert row[11] == "PAGO CON TARJETA EN SUPERMERCADOS"
    assert row[12] == "5678"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_structure.py tests/test_importer.py -v`
Expected: FAIL (`No module named finance.ingestion.structure`).

- [ ] **Step 3: Implement**

```python
# apps/api/finance/ingestion/structure.py
"""Split a bank line into what categorization reads; the card number stays in description_raw."""

import re

from pydantic import BaseModel

from finance.models import Bank

_CARD_NUMBER = re.compile(r"\b\d{12,19}\b")
_SPACES = re.compile(r"\s+")


class Structured(BaseModel):
    bank_concept: str | None
    merchant: str | None
    card_last4: str | None


def structure(bank: Bank, description_raw: str, merchant: str | None) -> Structured:
    """BBVA prints its own operation label before ' | '; CaixaBank has none."""
    concept = None
    if bank == "bbva" and " | " in description_raw:
        concept = description_raw.split(" | ", 1)[0]
    card = _CARD_NUMBER.search(merchant or "")
    cleaned = _SPACES.sub(" ", _CARD_NUMBER.sub("", merchant or "")).strip() or None
    return Structured(
        bank_concept=concept, merchant=cleaned, card_last4=card.group()[-4:] if card else None
    )
```

In `apps/api/finance/ingestion/importer.py`, replace `_INSERT_TRANSACTION` and the loop body of `transaction_rows`:

```python
_INSERT_TRANSACTION = """
insert into transactions (account_id, import_id, booked_at, value_date, amount, currency,
                          description_raw, merchant, balance_after, dedup_key, tx_type,
                          bank_concept, card_last4)
values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
on conflict (dedup_key) do nothing
"""
```

```python
    for tx, index in zip(parsed.transactions, occurrence_indexes(parsed.transactions), strict=True):
        parts = structure(parsed.header.bank, tx.description_raw, tx.merchant)
        rows.append(
            (
                account_id,
                import_id,
                tx.booked_at,
                tx.value_date,
                tx.amount,
                tx.currency,
                tx.description_raw,
                parts.merchant,
                tx.balance_after,
                dedup_key(parsed.header.iban, tx, index),
                "income" if tx.amount > 0 else "expense",
                parts.bank_concept,
                parts.card_last4,
            )
        )
```

Add `from finance.ingestion.structure import structure` to the imports.

- [ ] **Step 4: Run unit tests and lint**

Run: `cd apps/api && uv run task test && uv run task lint`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/ingestion/structure.py apps/api/finance/ingestion/importer.py apps/api/tests/test_structure.py apps/api/tests/test_importer.py
git commit -m "feat: store the bank concept and card last four at import, never the card number"
```

### Task 3: Taxonomy and rule seeds, `finance seed`

**Files:**
- Create: `supabase/seed/categories.yaml` (generated), `supabase/seed/rules.yaml`
- Create: `apps/api/finance/categorization/__init__.py` (empty), `taxonomy.py`, `rules.py`, `seed.py`
- Modify: `apps/api/finance/cli.py`, `apps/api/pyproject.toml` (add `pyyaml`)
- Test: `apps/api/tests/test_taxonomy.py`

**Interfaces:**
- Produces: `Category(slug: str, tx_type: Literal["expense","income","transfer"], level1: str, what: str, not_for: str | None = None)`; `Direction = Literal["outgoing","incoming"]`; `direction_of(amount: Decimal) -> Direction`.
- Produces: `Taxonomy(categories: list[Category])` with `get(slug) -> Category`, `leaves(direction) -> list[Category]`, `fits(slug, direction) -> bool`, `level1_sums(probabilities: dict[str, float]) -> dict[str, float]`, `tx_type_of(slug, amount) -> str`, `categories() -> list[Category]`.
- Produces: `read_categories_yaml(path) -> list[Category]`, `load_taxonomy(conn) -> Taxonomy`.
- Produces: `Rule(name, bank: Bank | None = None, match_field: Literal["bank_concept","merchant"], pattern: str, direction: Literal["outgoing","incoming","any"], category_slug: str)`; `read_rules_yaml(path) -> list[Rule]`; `load_rules(conn) -> list[Rule]`.
- Produces: `SEED_DIR`, `seed(conn) -> tuple[int, int]`; CLI `finance seed`.

- [ ] **Step 1: Generate the taxonomy YAML from the validated spike criteria**

Run from the repo root:

```bash
uv add --directory apps/api pyyaml
cd docs/superpowers/spikes/2026-09-23-jev-categorization && uv run --with typesafe-sdk --with 'psycopg[binary]' --with pyyaml python - <<'EOF'
import yaml
import run

header = (
    "# Two-level taxonomy (spec section 7), generated from the spike's validated criteria.\n"
    "# tx_type -> level 1 -> level-2 slug -> jev criterion (what, optional not_for).\n"
)
tree = {"expense": run.EXPENSE, "income": run.INCOME, "transfer": run.TRANSFER}
body = yaml.safe_dump(tree, sort_keys=False, allow_unicode=True, width=110)
open("../../../../supabase/seed/categories.yaml", "w").write(header + body)
EOF
```

Expected: `supabase/seed/categories.yaml` exists with 55 level-2 slugs (14 expense groups, `income`, `transfer`).

- [ ] **Step 2: Write the rules YAML**

```yaml
# supabase/seed/rules.yaml
# System rules (spec section 5): operations whose meaning the bank fixes and whose text names no
# merchant. Case-insensitive regex on the structured bank_concept or merchant. No fixture may be
# matched by two rules with different categories (tests/test_rules.py).
- {name: atm_withdrawal_concept, match_field: bank_concept, pattern: '^RET\. EFECTIVO', direction: outgoing, category_slug: atm_withdrawal}
- {name: atm_withdrawal_text, match_field: merchant, pattern: '^REINT\.? ?CAJERO', direction: outgoing, category_slug: atm_withdrawal}
- {name: card_settlement_concept, match_field: bank_concept, pattern: '^ADEUDO MENSUAL DE TARJETA', direction: outgoing, category_slug: credit_card_payment}
- {name: card_settlement_text, match_field: merchant, pattern: '^T\. (VISA|MASTERCARD)\b', direction: outgoing, category_slug: credit_card_payment}
- {name: bizum_sent_concept, match_field: bank_concept, pattern: '^BIZUM$', direction: outgoing, category_slug: payments_to_people}
- {name: bizum_sent_text, match_field: merchant, pattern: '^(BIZUM\b|ENVIADO:)', direction: outgoing, category_slug: payments_to_people}
- {name: bizum_received_concept, match_field: bank_concept, pattern: '^BIZUM$', direction: incoming, category_slug: payments_from_people}
- {name: bizum_received_text, match_field: merchant, pattern: '^(BIZUM\b|RECIBIDO:)', direction: incoming, category_slug: payments_from_people}
- {name: own_transfer_text, match_field: merchant, pattern: '^TRASPASO PROPIO\b', direction: any, category_slug: own_accounts}
```

- [ ] **Step 3: Write the failing tests**

```python
# apps/api/tests/test_taxonomy.py
from decimal import Decimal

from finance.categorization.rules import read_rules_yaml
from finance.categorization.seed import SEED_DIR
from finance.categorization.taxonomy import Taxonomy, direction_of, read_categories_yaml

CATEGORIES = read_categories_yaml(SEED_DIR / "categories.yaml")
TAXONOMY = Taxonomy(CATEGORIES)


def test_seed_has_the_spec_taxonomy():
    assert len(CATEGORIES) == 55
    assert len({c.slug for c in CATEGORIES}) == 55
    assert len({c.level1 for c in CATEGORIES if c.tx_type == "expense"}) == 14
    assert all(c.what for c in CATEGORIES)


def test_leaves_follow_the_direction():
    outgoing = {c.slug for c in TAXONOMY.leaves("outgoing")}
    incoming = {c.slug for c in TAXONOMY.leaves("incoming")}
    assert "groceries" in outgoing and "groceries" not in incoming
    assert "salary" in incoming and "salary" not in outgoing
    assert "own_accounts" in outgoing and "own_accounts" in incoming


def test_level1_sums_add_leaf_probabilities():
    sums = TAXONOMY.level1_sums({"groceries": 0.5, "fashion": 0.3, "restaurants_bars": 0.2})
    assert sums == {"shopping": 0.8, "leisure": 0.2}


def test_tx_type_comes_from_the_category_or_the_sign():
    assert TAXONOMY.tx_type_of("own_accounts", Decimal("-5")) == "transfer"
    assert TAXONOMY.tx_type_of("groceries", Decimal("-5")) == "expense"
    assert TAXONOMY.tx_type_of("refunds", Decimal("5")) == "income"
    assert direction_of(Decimal("-0.01")) == "outgoing"


def test_every_rule_points_to_a_known_category():
    slugs = {c.slug for c in CATEGORIES}
    assert {rule.category_slug for rule in read_rules_yaml(SEED_DIR / "rules.yaml")} <= slugs
```

- [ ] **Step 4: Run them to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_taxonomy.py -v`
Expected: FAIL (`No module named finance.categorization`).

- [ ] **Step 5: Implement taxonomy, rules and seed**

```python
# apps/api/finance/categorization/taxonomy.py
"""The two-level taxonomy: jev picks a level-2 slug, level 1 is derived (spec 5.1, 7)."""

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from psycopg import Connection
from pydantic import BaseModel

Direction = Literal["outgoing", "incoming"]
TxType = Literal["expense", "income", "transfer"]


class Category(BaseModel):
    slug: str
    tx_type: TxType
    level1: str
    what: str
    not_for: str | None = None


def direction_of(amount: Decimal) -> Direction:
    return "outgoing" if amount < 0 else "incoming"


class Taxonomy:
    def __init__(self, categories: list[Category]) -> None:
        self._by_slug = {category.slug: category for category in categories}

    def categories(self) -> list[Category]:
        return list(self._by_slug.values())

    def get(self, slug: str) -> Category:
        return self._by_slug[slug]

    def leaves(self, direction: Direction) -> list[Category]:
        """Options jev may pick: expense or income by direction, plus transfers."""
        kind = "expense" if direction == "outgoing" else "income"
        return [c for c in self._by_slug.values() if c.tx_type in (kind, "transfer")]

    def fits(self, slug: str, direction: Direction) -> bool:
        return any(category.slug == slug for category in self.leaves(direction))

    def level1_sums(self, probabilities: dict[str, float]) -> dict[str, float]:
        sums: dict[str, float] = defaultdict(float)
        for slug, probability in probabilities.items():
            sums[self._by_slug[slug].level1] += probability
        return {level1: round(total, 6) for level1, total in sums.items()}

    def tx_type_of(self, slug: str, amount: Decimal) -> TxType:
        if self._by_slug[slug].tx_type == "transfer":
            return "transfer"
        return "expense" if amount < 0 else "income"


def read_categories_yaml(path: Path) -> list[Category]:
    tree = yaml.safe_load(path.read_text())
    return [
        Category(slug=slug, tx_type=tx_type, level1=level1, **criterion)
        for tx_type, groups in tree.items()
        for level1, leaves in groups.items()
        for slug, criterion in leaves.items()
    ]


def load_taxonomy(conn: Connection) -> Taxonomy:
    rows = conn.execute("select slug, tx_type, level1, what, not_for from categories").fetchall()
    return Taxonomy([Category.model_validate(row) for row in rows])
```

```python
# apps/api/finance/categorization/rules.py
"""System rules: bank operations without a merchant, resolved before jev (spec 5)."""

from pathlib import Path
from typing import Literal

import yaml
from psycopg import Connection
from pydantic import BaseModel

from finance.models import Bank


class Rule(BaseModel):
    name: str
    bank: Bank | None = None
    match_field: Literal["bank_concept", "merchant"]
    pattern: str
    direction: Literal["outgoing", "incoming", "any"]
    category_slug: str


def read_rules_yaml(path: Path) -> list[Rule]:
    return [Rule.model_validate(item) for item in yaml.safe_load(path.read_text())]


def load_rules(conn: Connection) -> list[Rule]:
    rows = conn.execute(
        "select name, bank, match_field, pattern, direction, category_slug from rules"
        " where enabled order by name"
    ).fetchall()
    return [Rule.model_validate(row) for row in rows]
```

```python
# apps/api/finance/categorization/seed.py
"""Upsert the taxonomy and system rules from supabase/seed (run after every migration)."""

from psycopg import Connection

from finance.categorization.rules import read_rules_yaml
from finance.categorization.taxonomy import read_categories_yaml
from finance.settings import REPO_ROOT

SEED_DIR = REPO_ROOT / "supabase" / "seed"


def seed(conn: Connection) -> tuple[int, int]:
    categories = read_categories_yaml(SEED_DIR / "categories.yaml")
    rules = read_rules_yaml(SEED_DIR / "rules.yaml")
    with conn.transaction():
        for c in categories:
            conn.execute(
                "insert into categories (slug, tx_type, level1, what, not_for)"
                " values (%s, %s, %s, %s, %s) on conflict (slug) do update set"
                " tx_type = excluded.tx_type, level1 = excluded.level1,"
                " what = excluded.what, not_for = excluded.not_for",
                (c.slug, c.tx_type, c.level1, c.what, c.not_for),
            )
        for r in rules:
            conn.execute(
                "insert into rules (name, bank, match_field, pattern, direction, category_slug)"
                " values (%s, %s, %s, %s, %s, %s) on conflict (name) do update set"
                " bank = excluded.bank, match_field = excluded.match_field,"
                " pattern = excluded.pattern, direction = excluded.direction,"
                " category_slug = excluded.category_slug",
                (r.name, r.bank, r.match_field, r.pattern, r.direction, r.category_slug),
            )
    return len(categories), len(rules)
```

Add to `apps/api/finance/cli.py`:

```python
from finance.categorization.seed import seed as seed_database


@app.command("seed")
def seed_command() -> None:
    """Load the category taxonomy and system rules into the database."""
    with connection() as conn:
        categories, rules = seed_database(conn)
    typer.echo(f"categories={categories} rules={rules}")
```

- [ ] **Step 6: Run tests, lint, and seed the local database**

Run: `cd apps/api && uv run task test && uv run task lint && uv run finance seed`
Expected: tests PASS; `categories=55 rules=9`.

- [ ] **Step 7: Commit**

```bash
git add supabase/seed apps/api/finance/categorization apps/api/finance/cli.py apps/api/pyproject.toml apps/api/uv.lock apps/api/tests/test_taxonomy.py
git commit -m "feat: seed the two-level taxonomy with jev criteria and the system rules"
```

### Task 4: Match system rules

**Files:**
- Modify: `apps/api/finance/categorization/rules.py`
- Test: `apps/api/tests/test_rules.py`

**Interfaces:**
- Consumes: `Rule`, `read_rules_yaml`, `SEED_DIR`, `Direction`.
- Produces: `match_rule(rules: list[Rule], bank: Bank, bank_concept: str | None, merchant: str | None, direction: Direction) -> Rule | None` (first match in list order).

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/test_rules.py
import pytest

from finance.categorization.rules import match_rule, read_rules_yaml
from finance.categorization.seed import SEED_DIR

RULES = read_rules_yaml(SEED_DIR / "rules.yaml")

# (bank, bank_concept, merchant, direction, expected category or None). Synthetic text.
FIXTURES = [
    ("bbva", "RET. EFECTIVO A DEBITO CON TARJ. EN CAJERO. AUT.", "01820000 999", "outgoing", "atm_withdrawal"),
    ("caixabank", None, "REINT.CAJERO", "outgoing", "atm_withdrawal"),
    ("bbva", "ADEUDO MENSUAL DE TARJETA", None, "outgoing", "credit_card_payment"),
    ("caixabank", None, "T. VISA CLASSIC", "outgoing", "credit_card_payment"),
    ("bbva", "BIZUM", "ENVIADO: DINNER", "outgoing", "payments_to_people"),
    ("bbva", "BIZUM", "RECIBIDO: BIZUM DE ANA", "incoming", "payments_from_people"),
    ("caixabank", None, "BIZUM ENVIADO", "outgoing", "payments_to_people"),
    ("caixabank", None, "BIZUM RECIBIDO", "incoming", "payments_from_people"),
    ("caixabank", None, "ENVIADO: COMPRA SUPER", "outgoing", "payments_to_people"),
    ("caixabank", None, "TRASPASO PROPIO", "outgoing", "own_accounts"),
    ("caixabank", None, "TRASPASO PROPIO", "incoming", "own_accounts"),
    ("bbva", "PAGO CON TARJETA EN SUPERMERCADOS", "SUPER ACME 0042", "outgoing", None),
    ("bbva", "TRASPASO", "ANA EXAMPLE", "outgoing", None),
    ("bbva", "PAGO CON TARJETA EN RESTAURANTES Y CAFETERIAS", "BIZUMBAR", "outgoing", None),
    ("caixabank", None, "NOMINA (TRF)", "incoming", None),
]


@pytest.mark.parametrize(("bank", "concept", "merchant", "direction", "expected"), FIXTURES)
def test_seed_rules_on_fixtures(bank, concept, merchant, direction, expected):
    rule = match_rule(RULES, bank, concept, merchant, direction)
    assert (rule.category_slug if rule else None) == expected


@pytest.mark.parametrize(("bank", "concept", "merchant", "direction", "expected"), FIXTURES)
def test_no_fixture_matches_rules_with_different_categories(
    bank, concept, merchant, direction, expected
):
    categories = {
        rule.category_slug
        for rule in RULES
        if match_rule([rule], bank, concept, merchant, direction) is not None
    }
    assert len(categories) <= 1


def test_rule_limited_to_a_bank_ignores_other_banks():
    rule = RULES[0].model_copy(update={"bank": "caixabank"})
    assert match_rule([rule], "bbva", "RET. EFECTIVO X", None, "outgoing") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/api && uv run pytest tests/test_rules.py -v`
Expected: FAIL (`cannot import name 'match_rule'`).

- [ ] **Step 3: Implement**

Append to `apps/api/finance/categorization/rules.py` (add `import re`, `from finance.categorization.taxonomy import Direction`):

```python
def match_rule(
    rules: list[Rule],
    bank: Bank,
    bank_concept: str | None,
    merchant: str | None,
    direction: Direction,
) -> Rule | None:
    for rule in rules:
        if rule.bank not in (None, bank) or rule.direction not in ("any", direction):
            continue
        text = bank_concept if rule.match_field == "bank_concept" else merchant
        if text and re.search(rule.pattern, text, re.IGNORECASE):
            return rule
    return None
```

- [ ] **Step 4: Run tests and lint**

Run: `cd apps/api && uv run task test && uv run task lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/categorization/rules.py apps/api/tests/test_rules.py
git commit -m "feat: match system rules by bank concept or merchant text"
```

### Task 5: Pair transfers between imported accounts

**Files:**
- Create: `apps/api/finance/categorization/pairing.py`
- Modify: `apps/api/finance/settings.py`, `apps/api/tests/conftest.py`
- Test: `apps/api/tests/test_pairing.py`

**Interfaces:**
- Produces settings: `transfer_pattern: str = "TRASPASO|TRANSFER|BIZUM|TRF"`, `transfer_window_days: int = 2`.
- Produces: `PairCandidate(id: UUID, account_id: UUID, booked_at: date, amount: Decimal, description_raw: str)`; `find_pairs(rows, pattern: str, window_days: int) -> list[tuple[UUID, UUID]]` (outgoing id, incoming id); `pair_transfers(conn, settings) -> int`.
- Produces test fixtures in `conftest.py`: `db_conn` (rolled back) and `make_tx(amount, description_raw, *, iban=..., bank="bbva", booked_at=date(2026, 7, 1), merchant=None, bank_concept=None) -> UUID`.

- [ ] **Step 1: Add the shared database fixtures**

Append to `apps/api/tests/conftest.py`:

```python
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from finance.db import connection


@pytest.fixture
def db_conn():
    """A real local database connection; everything the test writes is rolled back."""
    with connection() as conn:
        with conn.transaction(force_rollback=True):
            yield conn


@pytest.fixture
def make_tx(db_conn):
    """Insert a synthetic transaction (fake IBAN) and return its id."""

    def _make(
        amount: str,
        description_raw: str,
        *,
        iban: str = "ES0000000000000000000001",
        bank: str = "bbva",
        booked_at: date = date(2026, 7, 1),
        merchant: str | None = None,
        bank_concept: str | None = None,
    ) -> UUID:
        account = db_conn.execute(
            "insert into accounts (bank, iban, name) values (%s, %s, %s)"
            " on conflict (iban) do update set name = excluded.name returning id",
            (bank, iban, f"test {iban[-4:]}"),
        ).fetchone()["id"]
        import_id = db_conn.execute(
            "insert into imports (account_id, filename, file_sha256, rows_total)"
            " values (%s, 'test.pdf', 'x', 1) returning id",
            (account,),
        ).fetchone()["id"]
        value = Decimal(amount)
        return db_conn.execute(
            "insert into transactions (account_id, import_id, booked_at, amount, description_raw,"
            " merchant, bank_concept, dedup_key, tx_type)"
            " values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning id",
            (account, import_id, booked_at, value, description_raw, merchant, bank_concept,
             uuid4().hex, "expense" if value < 0 else "income"),
        ).fetchone()["id"]

    return _make
```

- [ ] **Step 2: Write the failing tests**

```python
# apps/api/tests/test_pairing.py
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
        id=uuid4(), account_id=account, booked_at=date(2026, 7, day),
        amount=Decimal(amount), description_raw=text,
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
    second_out = _tx(A, "-50", "BIZUM ENVIADO", day=3)
    pairs = find_pairs([out, far, near, second_out], PATTERN, 2)
    assert (out.id, near.id) in pairs
    assert len({incoming for _, incoming in pairs}) == len(pairs)


@pytest.mark.integration
def test_pair_transfers_labels_both_sides_and_skips_user_labels(db_conn, make_tx):
    out = make_tx("-4321.09", "TRASPASO | ANA EXAMPLE", iban="ES0000000000000000000011")
    into = make_tx("4321.09", "TRASPASO | ANA EXAMPLE", iban="ES0000000000000000000012")
    mine = make_tx("-4321.08", "BIZUM ENVIADO", iban="ES0000000000000000000011")
    make_tx("4321.08", "BIZUM RECIBIDO", iban="ES0000000000000000000012")
    db_conn.execute(
        "update transactions set category_source = 'user', category_slug = 'payments_to_people'"
        " where id = %s", (mine,),
    )
    pair_transfers(db_conn, Settings())
    rows = db_conn.execute(
        "select id, tx_type, category_slug, category_source, transfer_pair_id from transactions"
        " where id = any(%s)", ([out, into, mine],),
    ).fetchall()
    by_id = {row["id"]: row for row in rows}
    assert by_id[out]["transfer_pair_id"] == by_id[into]["transfer_pair_id"] is not None
    assert by_id[out]["category_slug"] == "own_accounts" and by_id[out]["tx_type"] == "transfer"
    assert by_id[mine]["transfer_pair_id"] is None and by_id[mine]["category_source"] == "user"
```

- [ ] **Step 3: Run to verify failure**

Run: `cd apps/api && uv run pytest tests/test_pairing.py -v -m "not integration"`
Expected: FAIL (`No module named finance.categorization.pairing`).

- [ ] **Step 4: Implement settings and pairing**

Add to `Settings` in `apps/api/finance/settings.py`:

```python
    transfer_pattern: str = "TRASPASO|TRANSFER|BIZUM|TRF"
    transfer_window_days: int = 2
```

```python
# apps/api/finance/categorization/pairing.py
"""Money moving between two imported accounts is internal to the household (spec 4.4)."""

import re
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from psycopg import Connection
from pydantic import BaseModel

from finance.settings import Settings


class PairCandidate(BaseModel):
    id: UUID
    account_id: UUID
    booked_at: date
    amount: Decimal
    description_raw: str


def find_pairs(
    rows: list[PairCandidate], pattern: str, window_days: int
) -> list[tuple[UUID, UUID]]:
    """One-to-one (outgoing, incoming) pairs; the nearest booking date wins."""
    transfer = re.compile(pattern, re.IGNORECASE)
    eligible = [row for row in rows if transfer.search(row.description_raw)]
    outgoing = sorted((r for r in eligible if r.amount < 0), key=lambda r: (r.booked_at, str(r.id)))
    incoming = [r for r in eligible if r.amount > 0]
    used: set[UUID] = set()
    pairs = []
    for out in outgoing:
        candidates = [
            r
            for r in incoming
            if r.id not in used
            and r.account_id != out.account_id
            and r.amount == -out.amount
            and abs((r.booked_at - out.booked_at).days) <= window_days
        ]
        if candidates:
            best = min(candidates, key=lambda r: (abs((r.booked_at - out.booked_at).days), str(r.id)))
            used.add(best.id)
            pairs.append((out.id, best.id))
    return pairs


_CANDIDATES = """
select id, account_id, booked_at, amount, description_raw from transactions
where transfer_pair_id is null and category_source <> 'user' and description_raw ~* %s
"""

_LABEL_PAIR = """
update transactions set transfer_pair_id = %(pair)s, tx_type = 'transfer',
  category_slug = 'own_accounts', category_source = 'rule', category_confidence = 1,
  category_probabilities = null, merchant_id = null, merchant_source = 'none',
  is_subscription = false, needs_review = false, updated_at = now()
where id = any(%(ids)s)
"""


def pair_transfers(conn: Connection, settings: Settings) -> int:
    rows = conn.execute(_CANDIDATES, (settings.transfer_pattern,)).fetchall()
    candidates = [PairCandidate.model_validate(row) for row in rows]
    pairs = find_pairs(candidates, settings.transfer_pattern, settings.transfer_window_days)
    with conn.transaction():
        for out_id, in_id in pairs:
            conn.execute(_LABEL_PAIR, {"pair": uuid4(), "ids": [out_id, in_id]})
            for tx_id in (out_id, in_id):
                conn.execute(
                    "insert into transaction_labels (transaction_id, category_slug, source,"
                    " confidence) values (%s, 'own_accounts', 'rule', 1)",
                    (tx_id,),
                )
    return len(pairs)
```

- [ ] **Step 5: Run unit and integration tests, lint**

Run: `cd apps/api && uv run task test && uv run pytest tests/test_pairing.py -m integration -v && uv run task lint`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/categorization/pairing.py apps/api/finance/settings.py apps/api/tests/conftest.py apps/api/tests/test_pairing.py
git commit -m "feat: pair transfers and Bizum between imported accounts as household-internal"
```

### Task 6: jev questions and merchant fragments

**Files:**
- Create: `apps/api/finance/categorization/jev_questions.py`
- Test: `apps/api/tests/test_jev_questions.py`

**Interfaces:**
- Consumes: `Category`, `direction_of`.
- Produces: `tokens_of(text) -> list[str]`, `fragments(text, max_words=4) -> list[str]`, `match_key(name) -> str`, `significant_words(name) -> set[str]`, `jev_state(bank, bank_concept, merchant, amount: Decimal) -> dict`, `first_call_questions(leaves: list[Category], candidates: list[str]) -> dict[str, dict]`, `same_merchant_question(names: list[str]) -> dict[str, dict]`. Question specs are plain dicts `{"type": "choice" | "noul", "instructions": ..., "criteria": ...}`; Task 7 turns them into SDK objects.

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/test_jev_questions.py
from decimal import Decimal

from finance.categorization.jev_questions import (
    first_call_questions,
    fragments,
    jev_state,
    match_key,
    same_merchant_question,
    significant_words,
)
from finance.categorization.seed import SEED_DIR
from finance.categorization.taxonomy import Taxonomy, read_categories_yaml

TAXONOMY = Taxonomy(read_categories_yaml(SEED_DIR / "categories.yaml"))


def test_fragments_drop_codes_and_keep_word_runs():
    assert fragments("SUPER ACME 0042 L") == [
        "SUPER", "ACME", "SUPER ACME", "ACME L", "SUPER ACME L",
    ]


def test_fragments_split_web_prefixes_and_never_carry_digits():
    assert fragments("WWW.AMAZON* F641Z7X25") == ["WWW", "AMAZON", "WWW AMAZON"]
    assert fragments("1234567812345678 ACME") == ["ACME"]
    assert fragments("") == []


def test_match_key_ignores_spaces_and_punctuation():
    assert match_key("Mc Donald's") == match_key("MCDONALDS") == "MCDONALDS"


def test_significant_words_skip_legal_suffixes_and_short_words():
    assert significant_words("ACME FOODS SL DE") == {"ACME", "FOODS"}


def test_state_never_contains_a_card_number_field():
    state = jev_state("bbva", "PAGO CON TARJETA EN SUPERMERCADOS", "SUPER ACME", Decimal("-9.90"))
    assert state == {
        "bank": "bbva", "bank_concept": "PAGO CON TARJETA EN SUPERMERCADOS",
        "merchant_text": "SUPER ACME", "amount": "-9.90", "direction": "outgoing",
    }


def test_first_call_asks_three_independent_questions():
    leaves = TAXONOMY.leaves("outgoing")
    questions = first_call_questions(leaves, ["ACME", "SUPER ACME"])
    assert set(questions) == {"merchant_name", "category", "is_subscription"}
    assert set(questions["merchant_name"]["criteria"]) == {"ACME", "SUPER ACME", "none"}
    assert set(questions["category"]["criteria"]) == {c.slug for c in leaves}
    assert questions["category"]["criteria"]["groceries"]["group"] == "shopping"
    assert "not_for" not in questions["category"]["criteria"]["groceries"]
    assert "not_for" in questions["category"]["criteria"]["mortgage"]
    assert questions["is_subscription"]["type"] == "noul"
    assert "electricity" in questions["is_subscription"]["instructions"]["not_for"]


def test_same_merchant_question_offers_names_and_none():
    question = same_merchant_question(["ACME FOODS", "ACME BAR"])["known_merchant"]
    assert set(question["criteria"]) == {"ACME FOODS", "ACME BAR", "none"}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/api && uv run pytest tests/test_jev_questions.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement (wording copied from the validated spike, spec 5.1 and 6)**

```python
# apps/api/finance/categorization/jev_questions.py
"""What jev is asked (spec 5.1): code proposes the options, jev chooses."""

import re
from decimal import Decimal

from finance.categorization.taxonomy import Category, direction_of

_SPLIT = re.compile(r"[\s*/,]+|(?<=[A-Z])\.(?=[A-Z]{2})")
_HAS_DIGIT = re.compile(r"\d")
_FILLER = frozenset({"ES", "SL", "SA", "SAU", "N", "WWW", "COM", "DE", "DEL", "LA", "EL"})


def tokens_of(text: str) -> list[str]:
    """Words without punctuation, dropping reference codes (any token with a digit)."""
    words = (token.strip(".-_") for token in _SPLIT.split(text.upper()))
    return [word for word in words if word and not _HAS_DIGIT.search(word)]


def fragments(text: str, max_words: int = 4) -> list[str]:
    """Every run of 1..max_words consecutive words: the candidate names jev chooses from."""
    words = tokens_of(text)
    out: list[str] = []
    for size in range(1, max_words + 1):
        for start in range(len(words) - size + 1):
            fragment = " ".join(words[start : start + size])
            if re.search(r"[A-Z]{2}", fragment) and fragment not in out:
                out.append(fragment)
    return out


def match_key(name: str) -> str:
    """Exact-match key: MC DONALD'S == MCDONALDS."""
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def significant_words(name: str) -> set[str]:
    return {word for word in tokens_of(name) if word not in _FILLER and len(word) > 2}


def jev_state(bank: str, bank_concept: str | None, merchant: str | None, amount: Decimal) -> dict:
    return {
        "bank": bank,
        "bank_concept": bank_concept,
        "merchant_text": merchant or "",
        "amount": str(amount),
        "direction": direction_of(amount),
    }


def _criterion(category: Category) -> dict:
    criterion = {"group": category.level1, "what": category.what}
    if category.not_for:
        criterion["not_for"] = category.not_for
    return criterion


def first_call_questions(leaves: list[Category], candidates: list[str]) -> dict[str, dict]:
    """One call, three independent questions (speculative fan-out)."""
    return {
        "merchant_name": {
            "type": "choice",
            "instructions": {
                "question": "Which fragment of `merchant_text` is the business or brand name,"
                " as a person would say it?",
                "not_for": "city names, country codes, branch numbers, legal suffixes like SL or"
                " SA, card numbers",
            },
            "criteria": {candidate: None for candidate in candidates}
            | {
                "none": {
                    "what": "the text names no business: a person, a generic operation (BIZUM,"
                    " TRANSFER) or a code"
                }
            },
        },
        "category": {
            "type": "choice",
            "instructions": "Which category best describes this bank transaction",
            "criteria": {category.slug: _criterion(category) for category in leaves},
        },
        "is_subscription": {
            "type": "noul",
            "instructions": {
                "question": "This is a recurring charge for a service the person can cancel",
                "examples": "streaming, software and AI tools, telecom, gym, insurance,"
                " memberships",
                "not_for": "electricity, gas or water bills, rent, mortgage, loan repayments,"
                " one-off purchases",
            },
        },
    }


def same_merchant_question(names: list[str]) -> dict[str, dict]:
    return {
        "known_merchant": {
            "type": "choice",
            "instructions": {
                "question": "Is `candidate_name` the same business as one of these known"
                " merchants? Pick it, or none",
                "inspect": ["`candidate_name`", "`merchant_text`"],
                "note": "The same business can appear with branch, city or truncation suffixes",
                "not_for": "a different business that only shares the town, the street or the"
                " kind of shop",
            },
            "criteria": {name: None for name in names}
            | {"none": {"what": "a merchant not in this list"}},
        }
    }
```

- [ ] **Step 4: Run tests and lint**

Run: `cd apps/api && uv run task test && uv run task lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/categorization/jev_questions.py apps/api/tests/test_jev_questions.py
git commit -m "feat: build the jev merchant, category and subscription questions"
```

### Task 7: jev client with Langfuse tracing

**Files:**
- Create: `apps/api/finance/tracing.py`, `apps/api/finance/categorization/jev_client.py`
- Modify: `apps/api/pyproject.toml` (add `typesafe-sdk`, `langfuse`), `apps/api/finance/settings.py`
- Test: `apps/api/tests/test_jev_client.py`

**Interfaces:**
- Produces settings: `jev_concurrency: int = 8`.
- Produces: `JevAnswer(choice: str | None, confidence: float | None, probabilities: dict[str, float], noul: float | None)`; `JevResult(answers: dict[str, JevAnswer], model: str, request_id: str | None, input_tokens: int)`; `class Jev(Protocol): async def ask(self, name: str, state: dict, questions: dict[str, dict]) -> JevResult`.
- Produces: `to_sdk(questions) -> dict` and `TypesafeJev(api_key: str, concurrency: int = 8, tags: list[str] | None = None)`, an async context manager with `ask(...)` and an `input_tokens: int` counter.
- Produces: `langfuse() -> Langfuse` in `finance/tracing.py`.

- [ ] **Step 1: Add dependencies and check the current APIs**

Run: `cd apps/api && uv add typesafe-sdk langfuse`
Check with `context7`: typesafe-sdk `AsyncTypeSafeClient(api_key=...)`, `system_one(state=..., questions=...)`, answer fields `choice`, `confidence`, `probabilities`, `noul`, response `model`, `request_id`, `usage.input_tokens`; Langfuse v4 `get_client()`, `start_as_current_observation(as_type="generation", ...)`, `update(usage_details=...)`, `propagate_attributes(tags=...)`, `flush()`, and which environment variable sets the host (`LANGFUSE_BASE_URL` in v4). Adjust the code below only if an API differs.

- [ ] **Step 2: Write the failing tests**

```python
# apps/api/tests/test_jev_client.py
import asyncio
import os
from types import SimpleNamespace

import pytest
from typesafe_sdk import Choice, Noul

from finance.categorization.jev_client import TypesafeJev, _answer, to_sdk
from finance.categorization.jev_questions import same_merchant_question


def test_to_sdk_builds_choice_and_noul():
    built = to_sdk(
        {
            "a": {"type": "choice", "instructions": "q", "criteria": {"x": None, "y": None}},
            "b": {"type": "noul", "instructions": "yes or no"},
        }
    )
    assert isinstance(built["a"], Choice) and isinstance(built["b"], Noul)


def test_answer_reads_choice_and_noul_shapes():
    choice = _answer(SimpleNamespace(choice="x", confidence=0.9, probabilities={"x": 0.9, "y": 0.1}))
    noul = _answer(SimpleNamespace(noul=0.2))
    assert (choice.choice, choice.confidence, choice.noul) == ("x", 0.9, None)
    assert (noul.choice, noul.noul, noul.probabilities) == (None, 0.2, {})


@pytest.mark.integration
def test_real_jev_answers_a_synthetic_question():
    from finance.settings import get_settings

    key = get_settings().typesafe_api_key or os.environ.get("TYPESAFE_API_KEY")
    if not key:
        pytest.skip("no TYPESAFE_API_KEY")

    async def ask():
        async with TypesafeJev(key, tags=["test"]) as jev:
            state = {"merchant_text": "ACME FOODS", "candidate_name": "ACME"}
            return await jev.ask("same_merchant", state, same_merchant_question(["ACME FOODS"]))

    result = asyncio.run(ask())
    assert result.answers["known_merchant"].choice in {"ACME FOODS", "none"}
    assert result.model.startswith("jev")
```

- [ ] **Step 3: Run to verify failure**

Run: `cd apps/api && uv run pytest tests/test_jev_client.py -v -m "not integration"`
Expected: FAIL (module missing).

- [ ] **Step 4: Implement**

Add to `Settings`: `jev_concurrency: int = 8`.

```python
# apps/api/finance/tracing.py
"""Langfuse client configured from the repo-root .env (the SDK reads LANGFUSE_* variables)."""

import os
from functools import lru_cache

from langfuse import Langfuse, get_client

from finance.settings import get_settings


@lru_cache
def langfuse() -> Langfuse:
    settings = get_settings()
    values = {
        "LANGFUSE_PUBLIC_KEY": settings.langfuse_public_key,
        "LANGFUSE_SECRET_KEY": settings.langfuse_secret_key,
        "LANGFUSE_BASE_URL": settings.langfuse_base_url,
    }
    for name, value in values.items():
        if value:
            os.environ.setdefault(name, value)
    return get_client()
```

```python
# apps/api/finance/categorization/jev_client.py
"""jev System One behind a small protocol, so the categorizer can run with a fake in tests."""

import asyncio
from typing import Any, Protocol

from langfuse import propagate_attributes
from pydantic import BaseModel
from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul

from finance.tracing import langfuse


class JevAnswer(BaseModel):
    choice: str | None = None
    confidence: float | None = None
    probabilities: dict[str, float] = {}
    noul: float | None = None


class JevResult(BaseModel):
    answers: dict[str, JevAnswer]
    model: str
    request_id: str | None = None
    input_tokens: int = 0


class Jev(Protocol):
    async def ask(self, name: str, state: dict, questions: dict[str, dict]) -> JevResult: ...


def to_sdk(questions: dict[str, dict]) -> dict[str, Choice | Noul]:
    built: dict[str, Choice | Noul] = {}
    for name, spec in questions.items():
        if spec["type"] == "choice":
            built[name] = Choice(instructions=spec["instructions"], criteria=spec["criteria"])
        else:
            built[name] = Noul(instructions=spec["instructions"])
    return built


def _answer(raw: Any) -> JevAnswer:
    return JevAnswer(
        choice=getattr(raw, "choice", None),
        confidence=getattr(raw, "confidence", None),
        probabilities=dict(getattr(raw, "probabilities", None) or {}),
        noul=getattr(raw, "noul", None),
    )


class TypesafeJev:
    """Bounded concurrency, the SDK's default retry policy, one Langfuse generation per call."""

    def __init__(self, api_key: str, concurrency: int = 8, tags: list[str] | None = None) -> None:
        self._client = AsyncTypeSafeClient(api_key=api_key)
        self._semaphore = asyncio.Semaphore(concurrency)
        self._tags = tags or []
        self.input_tokens = 0

    async def __aenter__(self) -> "TypesafeJev":
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._client.__aexit__(*exc_info)
        langfuse().flush()

    async def ask(self, name: str, state: dict, questions: dict[str, dict]) -> JevResult:
        async with self._semaphore:
            with (
                propagate_attributes(tags=self._tags),
                langfuse().start_as_current_observation(
                    as_type="generation", name=f"jev.{name}", input=state
                ) as observation,
            ):
                response = await self._client.system_one(state=state, questions=to_sdk(questions))
                result = JevResult(
                    answers={key: _answer(value) for key, value in response.answers.items()},
                    model=response.model,
                    request_id=getattr(response, "request_id", None),
                    input_tokens=response.usage.input_tokens,
                )
                observation.update(
                    model=result.model,
                    output={k: a.model_dump(exclude_none=True) for k, a in result.answers.items()},
                    usage_details={"input": result.input_tokens},
                    metadata={"request_id": result.request_id},
                )
        self.input_tokens += result.input_tokens
        return result
```

- [ ] **Step 5: Run unit tests, the integration test once, and lint**

Run: `cd apps/api && uv run task test && uv run pytest tests/test_jev_client.py -m integration -v && uv run task lint`
Expected: PASS; one `jev.same_merchant` generation tagged `test` appears in Langfuse.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/tracing.py apps/api/finance/categorization/jev_client.py apps/api/finance/settings.py apps/api/pyproject.toml apps/api/uv.lock apps/api/tests/test_jev_client.py
git commit -m "feat: call jev through a traced client with bounded concurrency"
```

### Task 8: Merchant roster and resolution

**Files:**
- Create: `apps/api/finance/categorization/models.py`, `apps/api/finance/categorization/merchants.py`, `apps/api/tests/fakes.py`
- Modify: `apps/api/finance/settings.py`
- Test: `apps/api/tests/test_merchants.py`

**Interfaces:**
- Produces settings: `category_threshold: float = 0.95`, `brand_threshold: float = 0.5`, `merge_threshold: float = 0.8`, `merge_suggestion_floor: float = 0.5`, `subscription_threshold: float = 0.7`.
- Produces `models.py`: `TxInput(id, bank, booked_at, amount, description_raw, bank_concept=None, merchant=None, transfer_pair_id=None)`; `Categorization` (fields below); `CategorySource = Literal["rule","merchant","jev","user","none"]`.
- Produces `merchants.py`: `MerchantRef(id: UUID | None = None, name: str, category_slug: str | None = None, is_subscription: bool | None = None)`; `MerchantRoster(merchants)` with `get(name)`, `shortlist(name)`, `add(name)`, `new_merchants()`, `all()`; `MerchantResolution(merchant, confidence, merge_candidate, merge_confidence, dropped)`; `brand_confidence(answer: JevAnswer) -> float`; `async resolve_merchant(answer, state, roster, jev, settings) -> MerchantResolution`.
- Produces `tests/fakes.py`: `FakeJev(first=None, same=None, default=None)` and `jev_result(merchant=None, category=None, subscription=0.05, known=None) -> JevResult`.

- [ ] **Step 1: Write the test helpers**

```python
# apps/api/tests/fakes.py
"""A scripted jev for unit tests: no network, deterministic answers."""

from finance.categorization.jev_client import JevAnswer, JevResult


def _choice(probabilities: dict[str, float]) -> JevAnswer:
    choice = max(probabilities, key=probabilities.get)
    return JevAnswer(choice=choice, confidence=probabilities[choice], probabilities=probabilities)


def jev_result(
    *,
    merchant: dict[str, float] | None = None,
    category: dict[str, float] | None = None,
    subscription: float = 0.05,
    known: dict[str, float] | None = None,
) -> JevResult:
    answers = {"is_subscription": JevAnswer(noul=subscription)}
    if merchant is not None:
        answers["merchant_name"] = _choice(merchant)
    if category is not None:
        answers["category"] = _choice(category)
    if known is not None:
        answers["known_merchant"] = _choice(known)
    return JevResult(answers=answers, model="jev-test", request_id="req_test", input_tokens=100)


DEFAULT_RESULT = jev_result(merchant={"none": 1.0}, category={"uncategorized_expense": 0.3,
                                                              "other_income": 0.3,
                                                              "own_accounts": 0.4})


class FakeJev:
    """First-call answers keyed by merchant_text, same-merchant answers by candidate_name."""

    def __init__(self, first=None, same=None, default=DEFAULT_RESULT) -> None:
        self.first = first or {}
        self.same = same or {}
        self.default = default
        self.calls: list[tuple[str, dict]] = []

    async def ask(self, name: str, state: dict, questions: dict) -> JevResult:
        self.calls.append((name, dict(state)))
        if name == "categorize":
            return self.first.get(state["merchant_text"], self.default)
        return self.same[state["candidate_name"]]
```

- [ ] **Step 2: Write the failing tests**

```python
# apps/api/tests/test_merchants.py
import asyncio

from finance.categorization.merchants import MerchantRef, MerchantRoster, resolve_merchant
from finance.settings import Settings
from tests.fakes import FakeJev, jev_result

STATE = {"merchant_text": "ACME FOODS MADRID"}


def _resolve(merchant_probs, roster, jev=None):
    answer = jev_result(merchant=merchant_probs).answers["merchant_name"]
    return asyncio.run(resolve_merchant(answer, STATE, roster, jev or FakeJev(), Settings()))


def test_none_means_no_merchant():
    result = _resolve({"none": 0.9, "ACME": 0.1}, MerchantRoster([]))
    assert result.merchant is None and not result.dropped


def test_nested_fragments_add_up_and_create_a_new_merchant():
    roster = MerchantRoster([])
    result = _resolve({"ACME": 0.4, "ACME FOODS": 0.35, "MADRID": 0.25}, roster)
    assert result.merchant.name == "ACME" and result.merchant.id is None
    assert abs(result.confidence - 0.75) < 1e-9
    assert [m.name for m in roster.new_merchants()] == ["ACME"]


def test_brand_below_the_threshold_is_dropped():
    result = _resolve({"ACME": 0.45, "MADRID": 0.3, "none": 0.25}, MerchantRoster([]))
    assert result.merchant is None and result.dropped


def test_exact_key_reuses_a_known_merchant_without_asking_jev():
    known = MerchantRef(name="MC DONALD'S")
    jev = FakeJev()
    result = _resolve({"MCDONALDS": 0.9, "none": 0.1}, MerchantRoster([known]), jev)
    assert result.merchant is known and jev.calls == []


def test_same_merchant_answer_merges_suggests_or_creates():
    def run(confidence):
        roster = MerchantRoster([MerchantRef(name="ACME BAKERY")])
        same = {"ACME": jev_result(known={"ACME BAKERY": confidence, "none": 1 - confidence})}
        return _resolve({"ACME": 0.9, "none": 0.1}, roster, FakeJev(same=same))

    merged, suggested, separate = run(0.85), run(0.6), run(0.3)
    assert merged.merchant.name == "ACME BAKERY"
    assert suggested.merchant.name == "ACME" and suggested.merge_candidate.name == "ACME BAKERY"
    assert abs(suggested.merge_confidence - 0.6) < 1e-9
    assert separate.merchant.name == "ACME" and separate.merge_candidate is None
```

- [ ] **Step 3: Run to verify failure**

Run: `cd apps/api && uv run pytest tests/test_merchants.py -v`
Expected: FAIL (module missing).

- [ ] **Step 4: Implement**

Add to `Settings`:

```python
    category_threshold: float = 0.95
    brand_threshold: float = 0.5
    merge_threshold: float = 0.8
    merge_suggestion_floor: float = 0.5
    subscription_threshold: float = 0.7
```

```python
# apps/api/finance/categorization/models.py
"""Input and output of the categorizer; the database is not involved."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from finance.categorization.taxonomy import TxType
from finance.models import Bank

CategorySource = Literal["rule", "merchant", "jev", "user", "none"]


class TxInput(BaseModel):
    id: UUID
    bank: Bank
    booked_at: date
    amount: Decimal
    description_raw: str
    bank_concept: str | None = None
    merchant: str | None = None
    transfer_pair_id: UUID | None = None


class Categorization(BaseModel):
    transaction_id: UUID
    tx_type: TxType
    category_slug: str
    category_source: CategorySource
    category_confidence: float | None = None
    level1_confidence: float | None = None
    category_probabilities: dict[str, float] | None = None
    merchant_name: str | None = None
    merchant_source: Literal["jev", "user", "none"] = "none"
    merchant_confidence: float | None = None
    merge_candidate_name: str | None = None
    merge_confidence: float | None = None
    is_subscription: bool = False
    subscription_score: float | None = None
    transfer_pair_id: UUID | None = None
    needs_review: bool = False
    model: str | None = None
```

```python
# apps/api/finance/categorization/merchants.py
"""Name the merchant from jev's pick: exact key, then a same-merchant question (spec 5.1)."""

from uuid import UUID

from pydantic import BaseModel

from finance.categorization.jev_client import Jev, JevAnswer
from finance.categorization.jev_questions import (
    match_key,
    same_merchant_question,
    significant_words,
    tokens_of,
)
from finance.settings import Settings


class MerchantRef(BaseModel):
    id: UUID | None = None
    name: str
    category_slug: str | None = None
    is_subscription: bool | None = None


class MerchantRoster:
    """Known merchants by exact key. New ones are added in booking order, one at a time."""

    def __init__(self, merchants: list[MerchantRef]) -> None:
        self._by_key = {match_key(m.name): m for m in merchants}
        self._new: list[MerchantRef] = []

    def get(self, name: str) -> MerchantRef | None:
        return self._by_key.get(match_key(name))

    def shortlist(self, name: str) -> list[MerchantRef]:
        words = significant_words(name)
        return [m for m in self._by_key.values() if words & set(tokens_of(m.name))]

    def add(self, name: str) -> MerchantRef:
        merchant = MerchantRef(name=name)
        self._by_key[match_key(name)] = merchant
        self._new.append(merchant)
        return merchant

    def new_merchants(self) -> list[MerchantRef]:
        return list(self._new)

    def all(self) -> list[MerchantRef]:
        return list(self._by_key.values())


class MerchantResolution(BaseModel):
    merchant: MerchantRef | None = None
    confidence: float | None = None
    merge_candidate: MerchantRef | None = None
    merge_confidence: float | None = None
    dropped: bool = False


def brand_confidence(answer: JevAnswer) -> float:
    """Nested fragments (ACME, ACME FOODS) are all right: their probabilities add up."""
    chosen = answer.choice or "none"
    if chosen == "none":
        return 0.0
    return sum(
        p for f, p in answer.probabilities.items() if f != "none" and (f in chosen or chosen in f)
    )


async def resolve_merchant(
    answer: JevAnswer, state: dict, roster: MerchantRoster, jev: Jev, settings: Settings
) -> MerchantResolution:
    chosen = answer.choice
    if chosen in (None, "none"):
        return MerchantResolution()
    brand = brand_confidence(answer)
    if brand < settings.brand_threshold:
        return MerchantResolution(confidence=brand, dropped=True)
    if known := roster.get(chosen):
        return MerchantResolution(merchant=known, confidence=brand)
    shortlist = roster.shortlist(chosen)
    if shortlist:
        result = await jev.ask(
            "same_merchant",
            {**state, "candidate_name": chosen},
            same_merchant_question([m.name for m in shortlist]),
        )
        same = result.answers["known_merchant"]
        match = next((m for m in shortlist if m.name == same.choice), None)
        if match and same.confidence >= settings.merge_threshold:
            return MerchantResolution(merchant=match, confidence=same.confidence)
        if match and same.confidence >= settings.merge_suggestion_floor:
            return MerchantResolution(
                merchant=roster.add(chosen),
                confidence=brand,
                merge_candidate=match,
                merge_confidence=same.confidence,
            )
    return MerchantResolution(merchant=roster.add(chosen), confidence=brand)
```

- [ ] **Step 5: Run tests and lint**

Run: `cd apps/api && uv run task test && uv run task lint`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/categorization/models.py apps/api/finance/categorization/merchants.py apps/api/finance/settings.py apps/api/tests/fakes.py apps/api/tests/test_merchants.py
git commit -m "feat: resolve merchants by exact key and a same-merchant question"
```

### Task 9: The categorizer

**Files:**
- Create: `apps/api/finance/categorization/categorizer.py`
- Test: `apps/api/tests/test_categorizer.py`

**Interfaces:**
- Consumes: `Taxonomy`, `direction_of`, `Rule`, `match_rule`, `fragments`, `jev_state`, `first_call_questions`, `Jev`, `JevResult`, `MerchantRoster`, `MerchantResolution`, `resolve_merchant`, `TxInput`, `Categorization`, `Settings`.
- Produces: `CategorizationContext(taxonomy: Taxonomy, rules: list[Rule], settings: Settings)` (frozen dataclass); `from_rule(tx, slug, taxonomy) -> Categorization`; `decide(tx, first, resolution, ctx, use_merchant_defaults) -> Categorization`; `async categorize(rows, ctx, jev, roster, *, use_merchant_defaults=True) -> list[Categorization]` (same order as `rows`).

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/test_categorizer.py
import asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

from finance.categorization.categorizer import CategorizationContext, categorize
from finance.categorization.merchants import MerchantRef, MerchantRoster
from finance.categorization.models import TxInput
from finance.categorization.rules import read_rules_yaml
from finance.categorization.seed import SEED_DIR
from finance.categorization.taxonomy import Taxonomy, read_categories_yaml
from finance.settings import Settings
from tests.fakes import FakeJev, jev_result

CTX = CategorizationContext(
    taxonomy=Taxonomy(read_categories_yaml(SEED_DIR / "categories.yaml")),
    rules=read_rules_yaml(SEED_DIR / "rules.yaml"),
    settings=Settings(),
)
GROCERIES = jev_result(
    merchant={"ACME": 0.97, "none": 0.03}, category={"groceries": 0.97, "restaurants_bars": 0.03}
)


def _tx(merchant, amount="-9.90", concept="PAGO CON TARJETA EN SUPERMERCADOS", day=1, **extra):
    return TxInput(
        id=uuid4(), bank="bbva", booked_at=date(2026, 7, day), amount=Decimal(amount),
        description_raw=f"{concept} | {merchant}", bank_concept=concept, merchant=merchant, **extra
    )


def _run(rows, jev, roster=None, **kwargs):
    return asyncio.run(categorize(rows, CTX, jev, roster or MerchantRoster([]), **kwargs))


def test_paired_and_rule_rows_never_reach_jev():
    jev = FakeJev()
    paired = _tx("ANA EXAMPLE", concept="TRASPASO", transfer_pair_id=uuid4())
    bizum = _tx("ENVIADO: DINNER", concept="BIZUM")
    own, rule = _run([paired, bizum], jev)
    assert (own.category_slug, own.category_source, own.tx_type) == ("own_accounts", "rule", "transfer")
    assert (rule.category_slug, rule.needs_review) == ("payments_to_people", False)
    assert jev.calls == []


def test_confident_jev_row_is_accepted_and_names_a_new_merchant():
    [result] = _run([_tx("ACME 0042")], FakeJev(first={"ACME 0042": GROCERIES}))
    assert (result.category_slug, result.category_source, result.needs_review) == (
        "groceries", "jev", False,
    )
    assert result.merchant_name == "ACME" and result.merchant_source == "jev"
    assert result.level1_confidence == 0.97 and result.model == "jev-test"


def test_second_row_of_the_same_merchant_uses_the_exact_key():
    jev = FakeJev(first={"ACME 0042": GROCERIES, "ACME C.C.": GROCERIES})
    _run([_tx("ACME 0042", day=1), _tx("ACME C.C.", day=2)], jev)
    assert [name for name, _ in jev.calls] == ["categorize", "categorize"]


def test_below_the_threshold_goes_to_review_with_probabilities():
    unsure = jev_result(merchant={"ACME": 0.9, "none": 0.1},
                        category={"groceries": 0.9, "restaurants_bars": 0.1})
    [result] = _run([_tx("ACME")], FakeJev(first={"ACME": unsure}))
    assert result.needs_review and result.category_probabilities["restaurants_bars"] == 0.1


def test_dropped_brand_goes_to_review_without_a_merchant():
    weak = jev_result(merchant={"ACME": 0.4, "MADRID": 0.35, "none": 0.25},
                      category={"groceries": 0.99, "fashion": 0.01})
    [result] = _run([_tx("ACME MADRID")], FakeJev(first={"ACME MADRID": weak}))
    assert result.merchant_name is None and result.needs_review


def test_merchant_default_wins_over_jev_and_is_ignored_in_evals():
    roster = MerchantRoster([MerchantRef(id=uuid4(), name="ACME", category_slug="restaurants_bars",
                                         is_subscription=False)])
    jev = FakeJev(first={"ACME": GROCERIES})
    [with_default] = _run([_tx("ACME")], jev, roster)
    [without] = _run([_tx("ACME")], jev, MerchantRoster(roster.all()), use_merchant_defaults=False)
    assert (with_default.category_slug, with_default.category_source) == ("restaurants_bars", "merchant")
    assert with_default.category_probabilities["groceries"] == 0.97
    assert (without.category_slug, without.category_source) == ("groceries", "jev")


def test_expense_default_does_not_apply_to_a_refund():
    roster = MerchantRoster([MerchantRef(id=uuid4(), name="ACME", category_slug="fashion")])
    refund = jev_result(merchant={"ACME": 0.97, "none": 0.03}, category={"refunds": 0.97,
                                                                        "other_income": 0.03})
    [result] = _run([_tx("ACME", amount="13.77")], FakeJev(first={"ACME": refund}), roster)
    assert (result.category_slug, result.category_source, result.tx_type) == ("refunds", "jev", "income")


def test_subscription_flag_needs_an_expense_above_the_threshold():
    streaming = jev_result(merchant={"ACME TV": 0.99, "none": 0.01},
                           category={"entertainment": 0.99, "software_ai": 0.01}, subscription=0.9)
    jev = FakeJev(first={"ACME TV": streaming})
    [charge] = _run([_tx("ACME TV", concept="PAGO CON TARJETA")], jev)
    [refund] = _run([_tx("ACME TV", amount="9.99", concept="PAGO CON TARJETA")], jev)
    assert charge.is_subscription and charge.subscription_score == 0.9
    assert not refund.is_subscription
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/api && uv run pytest tests/test_categorizer.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# apps/api/finance/categorization/categorizer.py
"""The cascade without the database: pairing, system rules, jev, merchant defaults, gate."""

import asyncio
from dataclasses import dataclass
from uuid import UUID

from finance.categorization.jev_client import Jev, JevResult
from finance.categorization.jev_questions import first_call_questions, fragments, jev_state
from finance.categorization.merchants import MerchantResolution, MerchantRoster, resolve_merchant
from finance.categorization.models import Categorization, TxInput
from finance.categorization.rules import Rule, match_rule
from finance.categorization.taxonomy import Taxonomy, direction_of
from finance.settings import Settings


@dataclass(frozen=True)
class CategorizationContext:
    taxonomy: Taxonomy
    rules: list[Rule]
    settings: Settings


def from_rule(tx: TxInput, slug: str, taxonomy: Taxonomy) -> Categorization:
    return Categorization(
        transaction_id=tx.id,
        tx_type=taxonomy.tx_type_of(slug, tx.amount),
        category_slug=slug,
        category_source="rule",
        category_confidence=1.0,
        level1_confidence=1.0,
        transfer_pair_id=tx.transfer_pair_id,
    )


def decide(
    tx: TxInput,
    first: JevResult,
    resolution: MerchantResolution,
    ctx: CategorizationContext,
    use_merchant_defaults: bool,
) -> Categorization:
    taxonomy, settings = ctx.taxonomy, ctx.settings
    direction = direction_of(tx.amount)
    category = first.answers["category"]
    slug, confidence, source = category.choice, category.confidence, "jev"
    level1_confidence = taxonomy.level1_sums(category.probabilities).get(taxonomy.get(slug).level1)
    score = first.answers["is_subscription"].noul
    is_subscription = direction == "outgoing" and (score or 0) > settings.subscription_threshold
    merchant = resolution.merchant
    if use_merchant_defaults and merchant:
        # A default only applies in its own direction: an expense default never labels a refund.
        if merchant.category_slug and taxonomy.fits(merchant.category_slug, direction):
            slug, confidence, level1_confidence, source = merchant.category_slug, None, None, "merchant"
        if merchant.is_subscription is not None and direction == "outgoing":
            is_subscription = merchant.is_subscription
    below_threshold = source == "jev" and confidence < settings.category_threshold
    return Categorization(
        transaction_id=tx.id,
        tx_type=taxonomy.tx_type_of(slug, tx.amount),
        category_slug=slug,
        category_source=source,
        category_confidence=confidence,
        level1_confidence=level1_confidence,
        category_probabilities=category.probabilities,
        merchant_name=merchant.name if merchant else None,
        merchant_source="jev" if merchant else "none",
        merchant_confidence=resolution.confidence if merchant else None,
        merge_candidate_name=resolution.merge_candidate.name if resolution.merge_candidate else None,
        merge_confidence=resolution.merge_confidence,
        is_subscription=is_subscription,
        subscription_score=score,
        needs_review=below_threshold or resolution.dropped,
        model=first.model,
    )


async def categorize(
    rows: list[TxInput],
    ctx: CategorizationContext,
    jev: Jev,
    roster: MerchantRoster,
    *,
    use_merchant_defaults: bool = True,
) -> list[Categorization]:
    results: dict[UUID, Categorization] = {}
    pending: list[TxInput] = []
    for tx in rows:
        direction = direction_of(tx.amount)
        if tx.transfer_pair_id:
            results[tx.id] = from_rule(tx, "own_accounts", ctx.taxonomy)
        elif rule := match_rule(ctx.rules, tx.bank, tx.bank_concept, tx.merchant, direction):
            results[tx.id] = from_rule(tx, rule.category_slug, ctx.taxonomy)
        else:
            pending.append(tx)

    states = [jev_state(tx.bank, tx.bank_concept, tx.merchant, tx.amount) for tx in pending]
    firsts = await asyncio.gather(
        *(
            jev.ask(
                "categorize",
                state,
                first_call_questions(
                    ctx.taxonomy.leaves(direction_of(tx.amount)), fragments(tx.merchant or "")
                ),
            )
            for tx, state in zip(pending, states, strict=True)
        )
    )
    # Merchants are resolved one at a time in booking order, so each is created once.
    ordered = sorted(
        zip(pending, states, firsts, strict=True), key=lambda item: (item[0].booked_at, str(item[0].id))
    )
    for tx, state, first in ordered:
        resolution = await resolve_merchant(
            first.answers["merchant_name"], state, roster, jev, ctx.settings
        )
        results[tx.id] = decide(tx, first, resolution, ctx, use_merchant_defaults)
    return [results[tx.id] for tx in rows]
```

- [ ] **Step 4: Run tests and lint**

Run: `cd apps/api && uv run task test && uv run task lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/categorization/categorizer.py apps/api/tests/test_categorizer.py
git commit -m "feat: categorize transactions through rules, jev and merchant defaults"
```

### Task 10: Persist categorizations, `finance categorize`, run after every import

**Files:**
- Create: `apps/api/finance/categorization/store.py`, `apps/api/finance/api/categorize.py`
- Modify: `apps/api/finance/cli.py`, `apps/api/finance/api/imports.py`, `apps/api/finance/api/main.py`
- Test: `apps/api/tests/test_store.py`, `apps/api/tests/test_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 3–9, `pair_transfers`, `connection`, `get_settings`.
- Produces: `load_pending(conn, include_all: bool) -> list[TxInput]`; `load_roster(conn) -> MerchantRoster`; `save(conn, results, roster) -> None`; `CategorizeSummary(paired: int = 0, categorized: int = 0, needs_review: int = 0, by_source: dict[str, int] = {}, skipped: str | None = None)` with `line() -> str`; `async categorize_pending(conn, settings, include_all=False, jev: Jev | None = None) -> CategorizeSummary`; `run_categorization(include_all=False) -> CategorizeSummary`; `run_categorization_logged(include_all=False) -> None`.
- Produces: CLI `finance categorize [--all]`; `finance import` categorizes after importing; `POST /imports` schedules categorization as a background task; `POST /categorize/run?all=false` → 202 `{"status": "queued"}`.

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/test_store.py
import asyncio

import pytest

from finance.categorization.store import categorize_pending
from finance.settings import Settings
from tests.fakes import FakeJev, jev_result

pytestmark = pytest.mark.integration

ACME = jev_result(merchant={"ZZTEST ACME": 0.98, "none": 0.02},
                  category={"groceries": 0.98, "restaurants_bars": 0.02})


def _merchant_count(conn):
    return conn.execute(
        "select count(*) as n from merchants where match_key = 'ZZTESTACME'"
    ).fetchone()["n"]


def test_categorize_saves_labels_and_one_merchant(db_conn, make_tx):
    tx = make_tx("-9.90", "PAGO | ZZTEST ACME 0042", merchant="ZZTEST ACME 0042",
                 bank_concept="PAGO CON TARJETA EN SUPERMERCADOS")
    jev = FakeJev(first={"ZZTEST ACME 0042": ACME})
    asyncio.run(categorize_pending(db_conn, Settings(), jev=jev))
    row = db_conn.execute(
        "select category_slug, category_source, merchant_id, needs_review from transactions"
        " where id = %s", (tx,),
    ).fetchone()
    assert (row["category_slug"], row["category_source"], row["needs_review"]) == (
        "groceries", "jev", False,
    )
    assert row["merchant_id"] is not None and _merchant_count(db_conn) == 1
    label = db_conn.execute(
        "select source, model from transaction_labels where transaction_id = %s", (tx,)
    ).fetchone()
    assert (label["source"], label["model"]) == ("jev", "jev-test")


def test_rerun_all_keeps_user_labels_and_does_not_duplicate_merchants(db_conn, make_tx):
    tx = make_tx("-9.90", "PAGO | ZZTEST ACME 0042", merchant="ZZTEST ACME 0042")
    mine = make_tx("-5.00", "PAGO | ZZTEST ACME 0042", merchant="ZZTEST ACME 0042")
    db_conn.execute(
        "update transactions set category_source = 'user', category_slug = 'fashion'"
        " where id = %s", (mine,),
    )
    jev = FakeJev(first={"ZZTEST ACME 0042": ACME})
    asyncio.run(categorize_pending(db_conn, Settings(), jev=jev))
    asyncio.run(categorize_pending(db_conn, Settings(), include_all=True, jev=jev))
    row = db_conn.execute(
        "select category_slug, category_source from transactions where id = %s", (mine,)
    ).fetchone()
    assert (row["category_slug"], row["category_source"]) == ("fashion", "user")
    assert _merchant_count(db_conn) == 1
    assert db_conn.execute("select category_source from transactions where id = %s",
                           (tx,)).fetchone()["category_source"] == "jev"


def test_without_a_jev_key_rows_stay_pending(db_conn, make_tx):
    tx = make_tx("-9.90", "PAGO | ZZTEST ACME", merchant="ZZTEST ACME")
    summary = asyncio.run(categorize_pending(db_conn, Settings(typesafe_api_key=None)))
    assert summary.skipped
    row = db_conn.execute("select category_source from transactions where id = %s",
                          (tx,)).fetchone()
    assert row["category_source"] == "none"
```

Append to `apps/api/tests/test_cli.py` (merge the imports with the existing ones):

```python
from typer.testing import CliRunner

from finance import cli
from finance.models import ImportSummary


def test_import_succeeds_even_when_categorization_fails(monkeypatch, tmp_path):
    pdf = tmp_path / "statement.pdf"
    pdf.write_bytes(b"%PDF")
    summary = ImportSummary(
        import_id="00000000-0000-0000-0000-000000000001",
        account_id="00000000-0000-0000-0000-000000000002",
        bank="bbva", iban_last4="0001", filename="statement.pdf",
        rows_total=1, rows_new=1, rows_duplicate=0,
    )

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _fail(include_all=False):
        raise RuntimeError("jev is down")

    monkeypatch.setattr(cli, "connection", lambda: _Conn())
    monkeypatch.setattr(cli, "import_statement", lambda *args: summary)
    monkeypatch.setattr(cli, "run_categorization", _fail)
    result = CliRunner().invoke(cli.app, ["import", str(pdf)])
    assert result.exit_code == 0
    assert "new=1" in result.output and "categorization failed: jev is down" in result.output
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/api && uv run pytest tests/test_cli.py -v && uv run pytest tests/test_store.py -m integration -v`
Expected: FAIL (`run_categorization` and `finance.categorization.store` missing).

- [ ] **Step 3: Implement the store**

```python
# apps/api/finance/categorization/store.py
"""Load what needs a category, run the categorizer, save results and label history."""

import asyncio
import logging
from collections import Counter

from psycopg import Connection
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from finance.categorization.categorizer import CategorizationContext, categorize
from finance.categorization.jev_client import Jev, TypesafeJev
from finance.categorization.jev_questions import match_key
from finance.categorization.merchants import MerchantRef, MerchantRoster
from finance.categorization.models import Categorization, TxInput
from finance.categorization.pairing import pair_transfers
from finance.categorization.rules import load_rules
from finance.categorization.taxonomy import load_taxonomy
from finance.db import connection
from finance.settings import Settings, get_settings

logger = logging.getLogger(__name__)

_PENDING = """
select t.id, a.bank, t.booked_at, t.amount, t.description_raw, t.bank_concept, t.merchant,
       t.transfer_pair_id
from transactions t join accounts a on a.id = t.account_id
where t.category_source = 'none' or (%(all)s and t.category_source <> 'user')
order by t.booked_at, t.id
"""

_UPDATE = """
update transactions set tx_type = %(tx_type)s, category_slug = %(category_slug)s,
  category_source = %(category_source)s, category_confidence = %(category_confidence)s,
  category_probabilities = %(category_probabilities)s, merchant_id = %(merchant_id)s,
  merchant_source = %(merchant_source)s, merchant_confidence = %(merchant_confidence)s,
  is_subscription = %(is_subscription)s, subscription_score = %(subscription_score)s,
  needs_review = %(needs_review)s, updated_at = now()
where id = %(id)s and category_source <> 'user'
"""

_LABEL = """
insert into transaction_labels (transaction_id, merchant_id, category_slug, is_subscription,
                                source, confidence, model)
values (%s, %s, %s, %s, %s, %s, %s)
"""


class CategorizeSummary(BaseModel):
    paired: int = 0
    categorized: int = 0
    needs_review: int = 0
    by_source: dict[str, int] = {}
    skipped: str | None = None

    def line(self) -> str:
        if self.skipped:
            return f"categorization skipped: {self.skipped} (paired={self.paired})"
        sources = " ".join(f"{k}={v}" for k, v in sorted(self.by_source.items()))
        return (
            f"paired={self.paired} categorized={self.categorized} {sources}"
            f" needs_review={self.needs_review}"
        )


def load_pending(conn: Connection, include_all: bool) -> list[TxInput]:
    rows = conn.execute(_PENDING, {"all": include_all}).fetchall()
    return [TxInput.model_validate(row) for row in rows]


def load_roster(conn: Connection) -> MerchantRoster:
    rows = conn.execute("select id, name, category_slug, is_subscription from merchants").fetchall()
    return MerchantRoster([MerchantRef.model_validate(row) for row in rows])


def _merchant_ids(conn: Connection, roster: MerchantRoster) -> dict[str, object]:
    ids = {m.name: m.id for m in roster.all() if m.id}
    for merchant in roster.new_merchants():
        ids[merchant.name] = conn.execute(
            "insert into merchants (name, match_key) values (%s, %s)"
            " on conflict (match_key) do update set match_key = excluded.match_key returning id",
            (merchant.name, match_key(merchant.name)),
        ).fetchone()["id"]
    return ids


def save(conn: Connection, results: list[Categorization], roster: MerchantRoster) -> None:
    with conn.transaction():
        ids = _merchant_ids(conn, roster)
        for r in results:
            merchant_id = ids.get(r.merchant_name) if r.merchant_name else None
            params = r.model_dump(include={
                "tx_type", "category_slug", "category_source", "category_confidence",
                "merchant_source", "merchant_confidence", "is_subscription", "subscription_score",
                "needs_review",
            })
            params |= {
                "id": r.transaction_id,
                "merchant_id": merchant_id,
                "category_probabilities": Jsonb(r.category_probabilities)
                if r.category_probabilities else None,
            }
            conn.execute(_UPDATE, params)
            if r.merge_candidate_name and merchant_id:
                conn.execute(
                    "update merchants set merge_candidate_id = %s, merge_confidence = %s"
                    " where id = %s and not confirmed",
                    (ids[r.merge_candidate_name], r.merge_confidence, merchant_id),
                )
            conn.execute(
                _LABEL,
                (r.transaction_id, merchant_id, r.category_slug, r.is_subscription,
                 r.category_source, r.category_confidence, r.model),
            )


async def categorize_pending(
    conn: Connection, settings: Settings, include_all: bool = False, jev: Jev | None = None
) -> CategorizeSummary:
    paired = pair_transfers(conn, settings)
    rows = load_pending(conn, include_all)
    if not rows:
        return CategorizeSummary(paired=paired)
    if jev is None and not settings.typesafe_api_key:
        return CategorizeSummary(paired=paired, skipped="TYPESAFE_API_KEY is not set")
    ctx = CategorizationContext(load_taxonomy(conn), load_rules(conn), settings)
    roster = load_roster(conn)
    if jev is None:
        async with TypesafeJev(settings.typesafe_api_key, settings.jev_concurrency) as client:
            results = await categorize(rows, ctx, client, roster)
    else:
        results = await categorize(rows, ctx, jev, roster)
    save(conn, results, roster)
    return CategorizeSummary(
        paired=paired,
        categorized=len(results),
        needs_review=sum(r.needs_review for r in results),
        by_source=dict(Counter(r.category_source for r in results)),
    )


def run_categorization(include_all: bool = False) -> CategorizeSummary:
    with connection() as conn:
        return asyncio.run(categorize_pending(conn, get_settings(), include_all))


def run_categorization_logged(include_all: bool = False) -> None:
    """Background-task entry point: an import must never fail because of categorization."""
    try:
        logger.info(run_categorization(include_all).line())
    except Exception:
        logger.exception("categorization failed")
```

- [ ] **Step 4: Wire the CLI, the import route and `POST /categorize/run`**

In `apps/api/finance/cli.py` add `from finance.categorization.store import run_categorization`, then at the end of `import_statements` (before `if failed:`):

```python
    try:
        typer.echo(run_categorization().line())
    except Exception as error:  # the import itself already succeeded
        typer.echo(f"categorization failed: {error}")
```

and the command:

```python
@app.command("categorize")
def categorize_command(
    include_all: bool = typer.Option(
        False, "--all", help="Re-run every transaction you have not labelled yourself."
    ),
) -> None:
    """Categorize pending transactions (pairing, rules, jev)."""
    typer.echo(run_categorization(include_all).line())
```

In `apps/api/finance/api/imports.py`:

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile

from finance.categorization.store import run_categorization_logged


@router.post("", status_code=201)
def create_import(file: UploadFile, conn: Db, background: BackgroundTasks) -> ImportSummary:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF statements are supported")
    try:
        summary = import_statement(file.file.read(), file.filename or "statement.pdf", conn)
    except (UnsupportedStatement, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    background.add_task(run_categorization_logged)
    return summary
```

```python
# apps/api/finance/api/categorize.py
"""Re-run the categorization cascade in the background."""

from fastapi import APIRouter, BackgroundTasks

from finance.categorization.store import run_categorization_logged

router = APIRouter(prefix="/categorize", tags=["categorize"])


@router.post("/run", status_code=202)
def run(background: BackgroundTasks, all: bool = False) -> dict[str, str]:
    background.add_task(run_categorization_logged, all)
    return {"status": "queued"}
```

Register it in `apps/api/finance/api/main.py`: `from finance.api import accounts, categorize, imports, transactions` and `app.include_router(categorize.router)`.

- [ ] **Step 5: Run everything and try it on the real ledger**

Run: `cd apps/api && uv run task test && uv run task test-integration && uv run task lint`
Expected: PASS.
Run: `cd apps/api && uv run finance categorize`
Expected: a line like `paired=6 categorized=400 jev=... rule=... needs_review=...` (about $0.05; Langfuse shows one generation per call).

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/categorization/store.py apps/api/finance/api apps/api/finance/cli.py apps/api/tests/test_store.py apps/api/tests/test_cli.py
git commit -m "feat: categorize after every import and on demand, never over user labels"
```

### Task 11: Learning from user labels

**Files:**
- Create: `apps/api/finance/categorization/labels.py`
- Test: `apps/api/tests/test_labels.py`

**Interfaces:**
- Consumes: `match_key`.
- Produces: `NotFound(LookupError)`; `get_or_create_merchant(conn, name) -> UUID`; `label_transaction(conn, transaction_id, category_slug, is_subscription, merchant_id=None, new_merchant_name=None) -> None`; `confirm_merchant(conn, merchant_id, category_slug, is_subscription, name=None, merge_into_id=None) -> UUID` (returns the merchant that holds the default); `merge_merchants(conn, source_id, into_id) -> None`; `dismiss_merge(conn, merchant_id) -> None`.
- Semantics (spec 5.3): a merchant confirm sets the merchant default and relabels that merchant's rows with `category_source` in `jev`, `merchant`, `none` whose direction fits the category; those rows get `category_source = 'merchant'` (they follow the default later) and a `transaction_labels` row with `source = 'user'` (the user reviewed them: golden set). One-off labels set `category_source = 'user'` and never touch the default.

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/test_labels.py
import pytest

from finance.categorization.labels import (
    confirm_merchant,
    dismiss_merge,
    label_transaction,
    merge_merchants,
)

pytestmark = pytest.mark.integration


def _merchant(conn, name, **columns):
    row = conn.execute(
        "insert into merchants (name, match_key) values (%s, %s) returning id",
        (name, "".join(ch for ch in name.upper() if ch.isalnum())),
    ).fetchone()
    for column, value in columns.items():
        conn.execute(f"update merchants set {column} = %s where id = %s", (value, row["id"]))
    return row["id"]


def _set(conn, tx, **columns):
    for column, value in columns.items():
        conn.execute(f"update transactions set {column} = %s where id = %s", (value, tx))


def _row(conn, tx):
    return conn.execute("select * from transactions where id = %s", (tx,)).fetchone()


def test_confirm_sets_the_default_and_relabels_reviewed_rows(db_conn, make_tx):
    acme = _merchant(db_conn, "ZZTEST ACME")
    charge = make_tx("-9.90", "PAGO | ZZTEST ACME")
    refund = make_tx("9.90", "DEVOLUCION | ZZTEST ACME")
    mine = make_tx("-5.00", "PAGO | ZZTEST ACME")
    _set(db_conn, charge, merchant_id=acme, category_source="jev", category_slug="groceries",
         needs_review=True)
    _set(db_conn, refund, merchant_id=acme, category_source="jev", category_slug="refunds")
    _set(db_conn, mine, merchant_id=acme, category_source="user", category_slug="fashion")

    confirm_merchant(db_conn, acme, "restaurants_bars", False)

    assert (_row(db_conn, charge)["category_slug"], _row(db_conn, charge)["category_source"]) == (
        "restaurants_bars", "merchant",
    )
    assert _row(db_conn, charge)["needs_review"] is False
    assert _row(db_conn, refund)["category_slug"] == "refunds"
    assert _row(db_conn, mine)["category_slug"] == "fashion"
    merchant = db_conn.execute("select * from merchants where id = %s", (acme,)).fetchone()
    assert (merchant["category_slug"], merchant["confirmed"]) == ("restaurants_bars", True)
    label = db_conn.execute(
        "select source from transaction_labels where transaction_id = %s", (charge,)
    ).fetchone()
    assert label["source"] == "user"


def test_one_off_label_creates_a_merchant_and_leaves_defaults_alone(db_conn, make_tx):
    acme = _merchant(db_conn, "ZZTEST ACME", category_slug="groceries")
    tx = make_tx("-30.00", "PAGO | ZZTEST ACME")
    _set(db_conn, tx, merchant_id=acme, category_source="merchant", category_slug="groceries")

    label_transaction(db_conn, tx, "home_goods", False, new_merchant_name="ZZTEST ACME HOME")

    row = _row(db_conn, tx)
    assert (row["category_slug"], row["category_source"], row["merchant_source"]) == (
        "home_goods", "user", "user",
    )
    assert row["merchant_id"] != acme
    default = db_conn.execute("select category_slug from merchants where id = %s", (acme,))
    assert default.fetchone()["category_slug"] == "groceries"


def test_merge_repoints_rows_and_keeps_the_target_default(db_conn, make_tx):
    source = _merchant(db_conn, "ZZTEST ACME FOODS", category_slug="fashion")
    target = _merchant(db_conn, "ZZTEST ACME", category_slug="groceries")
    tx = make_tx("-9.90", "PAGO | ZZTEST ACME FOODS")
    _set(db_conn, tx, merchant_id=source)

    merge_merchants(db_conn, source, target)

    assert _row(db_conn, tx)["merchant_id"] == target
    assert db_conn.execute("select 1 from merchants where id = %s", (source,)).fetchone() is None
    kept = db_conn.execute("select category_slug from merchants where id = %s", (target,))
    assert kept.fetchone()["category_slug"] == "groceries"


def test_renaming_to_an_existing_merchant_merges(db_conn, make_tx):
    source = _merchant(db_conn, "ZZTEST ACME 2")
    target = _merchant(db_conn, "ZZTEST ACME")
    tx = make_tx("-9.90", "PAGO | ZZTEST ACME 2")
    _set(db_conn, tx, merchant_id=source, category_source="jev", category_slug="fashion")

    holder = confirm_merchant(db_conn, source, "groceries", False, name="zztest acme")

    assert holder == target and _row(db_conn, tx)["merchant_id"] == target


def test_dismiss_merge_confirms_the_merchant(db_conn):
    target = _merchant(db_conn, "ZZTEST ACME")
    source = _merchant(db_conn, "ZZTEST ACME BAR", merge_candidate_id=target, merge_confidence=0.6)
    dismiss_merge(db_conn, source)
    row = db_conn.execute("select * from merchants where id = %s", (source,)).fetchone()
    assert (row["confirmed"], row["merge_candidate_id"]) == (True, None)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/api && uv run pytest tests/test_labels.py -m integration -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# apps/api/finance/categorization/labels.py
"""What a user label does (spec 5.3): one transaction, or a whole merchant as its default."""

from uuid import UUID

from psycopg import Connection

from finance.categorization.jev_questions import match_key


class NotFound(LookupError):
    pass


_TX_TYPE = (
    "case when c.tx_type = 'transfer' then 'transfer'"
    " when t.amount < 0 then 'expense' else 'income' end"
)

_LABEL_ONE = f"""
update transactions t set category_slug = c.slug, category_source = 'user',
  category_confidence = null, tx_type = {_TX_TYPE},
  is_subscription = %(sub)s and t.amount < 0,
  merchant_id = coalesce(%(merchant)s, t.merchant_id),
  merchant_source = case when %(merchant)s::uuid is null then t.merchant_source else 'user' end,
  needs_review = false, updated_at = now()
from categories c
where c.slug = %(slug)s and t.id = %(id)s
returning t.merchant_id
"""

_RELABEL_MERCHANT = f"""
update transactions t set category_slug = c.slug, category_source = 'merchant',
  category_confidence = null, tx_type = {_TX_TYPE},
  is_subscription = case when t.amount < 0 then %(sub)s else false end,
  needs_review = false, updated_at = now()
from categories c
where c.slug = %(slug)s and t.merchant_id = %(merchant)s
  and t.category_source in ('jev', 'merchant', 'none')
  and c.tx_type in ('transfer', case when t.amount < 0 then 'expense' else 'income' end)
returning t.id
"""

_USER_LABEL = """
insert into transaction_labels (transaction_id, merchant_id, category_slug, is_subscription, source)
values (%s, %s, %s, %s, 'user')
"""


def get_or_create_merchant(conn: Connection, name: str) -> UUID:
    return conn.execute(
        "insert into merchants (name, match_key) values (%s, %s)"
        " on conflict (match_key) do update set match_key = excluded.match_key returning id",
        (name.strip(), match_key(name)),
    ).fetchone()["id"]


def label_transaction(
    conn: Connection,
    transaction_id: UUID,
    category_slug: str,
    is_subscription: bool,
    merchant_id: UUID | None = None,
    new_merchant_name: str | None = None,
) -> None:
    with conn.transaction():
        if new_merchant_name:
            merchant_id = get_or_create_merchant(conn, new_merchant_name)
        params = {"slug": category_slug, "sub": is_subscription, "merchant": merchant_id,
                  "id": transaction_id}
        row = conn.execute(_LABEL_ONE, params).fetchone()
        if row is None:
            raise NotFound(f"transaction {transaction_id} or category {category_slug}")
        conn.execute(
            _USER_LABEL, (transaction_id, row["merchant_id"], category_slug, is_subscription)
        )


def merge_merchants(conn: Connection, source_id: UUID, into_id: UUID) -> None:
    ids = {"src": source_id, "into": into_id}
    with conn.transaction():
        found = conn.execute(
            "select count(*) as n from merchants where id = any(%s)", ([source_id, into_id],)
        ).fetchone()["n"]
        if source_id == into_id or found != 2:
            raise NotFound(f"merchants {source_id} and {into_id}")
        conn.execute("update transactions set merchant_id = %(into)s where merchant_id = %(src)s", ids)
        conn.execute(
            "update transaction_labels set merchant_id = %(into)s where merchant_id = %(src)s", ids
        )
        conn.execute(
            "update merchants set merge_candidate_id = null, merge_confidence = null"
            " where merge_candidate_id = %(src)s", ids,
        )
        conn.execute(
            "update merchants i set category_slug = coalesce(i.category_slug, s.category_slug),"
            " is_subscription = coalesce(i.is_subscription, s.is_subscription), confirmed = true"
            " from merchants s where i.id = %(into)s and s.id = %(src)s", ids,
        )
        conn.execute("delete from merchants where id = %(src)s", ids)


def confirm_merchant(
    conn: Connection,
    merchant_id: UUID,
    category_slug: str,
    is_subscription: bool,
    name: str | None = None,
    merge_into_id: UUID | None = None,
) -> UUID:
    with conn.transaction():
        if name and merge_into_id is None:
            other = conn.execute(
                "select id from merchants where match_key = %s and id <> %s",
                (match_key(name), merchant_id),
            ).fetchone()
            if other:
                merge_into_id = other["id"]
            else:
                conn.execute(
                    "update merchants set name = %s, match_key = %s where id = %s",
                    (name.strip(), match_key(name), merchant_id),
                )
        if merge_into_id:
            merge_merchants(conn, merchant_id, merge_into_id)
            merchant_id = merge_into_id
        updated = conn.execute(
            "update merchants set category_slug = %s, is_subscription = %s, confirmed = true,"
            " merge_candidate_id = null, merge_confidence = null where id = %s returning id",
            (category_slug, is_subscription, merchant_id),
        ).fetchone()
        if updated is None:
            raise NotFound(f"merchant {merchant_id}")
        params = {"slug": category_slug, "sub": is_subscription, "merchant": merchant_id}
        # The rows on screen were reviewed by the user: they join the golden set.
        for row in conn.execute(_RELABEL_MERCHANT, params).fetchall():
            conn.execute(_USER_LABEL, (row["id"], merchant_id, category_slug, is_subscription))
    return merchant_id


def dismiss_merge(conn: Connection, merchant_id: UUID) -> None:
    row = conn.execute(
        "update merchants set confirmed = true, merge_candidate_id = null, merge_confidence = null"
        " where id = %s returning id",
        (merchant_id,),
    ).fetchone()
    if row is None:
        raise NotFound(f"merchant {merchant_id}")
```

- [ ] **Step 4: Run tests and lint**

Run: `cd apps/api && uv run task test && uv run pytest tests/test_labels.py -m integration -v && uv run task lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/categorization/labels.py apps/api/tests/test_labels.py
git commit -m "feat: learn from labels as merchant defaults, one-off labels and merges"
```

### Task 12: Review queue and its API

**Files:**
- Create: `apps/api/finance/categorization/review_queue.py`, `apps/api/finance/api/review.py`, `apps/api/finance/api/categories.py`, `apps/api/finance/api/merchants.py`
- Modify: `apps/api/finance/api/transactions.py`, `apps/api/finance/api/main.py`
- Test: `apps/api/tests/test_review_queue.py`, `apps/api/tests/test_api.py`, `apps/api/tests/test_review_api.py`

**Interfaces:**
- Consumes: `Taxonomy`, `load_taxonomy`, labels functions and `NotFound`, `Db`.
- Produces (pure, `review_queue.py`): `ReviewRow`, `ReviewTransaction(id, booked_at, amount, description_raw, account_name)`, `CategoryScore(slug, confidence)`, `Suggestion(category_slug, level1, confidence, is_subscription, top: list[CategoryScore])`, `MergeSuggestion(merchant_id, name, confidence)`, `MerchantOut(id, name)`, `ReviewItem(key, kind: Literal["merchant","transaction"], merchant, transactions, count, total, suggestion, merge)`; `suggestion_for(rows, taxonomy) -> Suggestion`; `build_review_items(rows, merges: dict[UUID, MergeSuggestion], taxonomy) -> list[ReviewItem]`.
- Produces routes: `GET /review -> list[ReviewItem]`, `GET /review/count -> ReviewCount(pending: int)`, `GET /categories -> list[CategoryOut(slug, tx_type, level1)]`, `GET /merchants?q=&limit= -> list[MerchantOut]`, `POST /merchants/{id}/review` (`ConfirmMerchant(category_slug, is_subscription, name=None, merge_into_id=None)`) → 204, `POST /merchants/{id}/merge` (`MergeRequest(into_id)`) → 204, `POST /merchants/{id}/dismiss-merge` → 204, `POST /transactions/{id}/label` (`LabelTransaction(category_slug, is_subscription=False, merchant_id=None, new_merchant_name=None)`) → 204. Unknown category → 422; unknown id → 404.

- [ ] **Step 1: Write the failing unit tests**

```python
# apps/api/tests/test_review_queue.py
from datetime import date
from decimal import Decimal
from uuid import uuid4

from finance.categorization.review_queue import MergeSuggestion, ReviewRow, build_review_items
from finance.categorization.seed import SEED_DIR
from finance.categorization.taxonomy import Taxonomy, read_categories_yaml

TAXONOMY = Taxonomy(read_categories_yaml(SEED_DIR / "categories.yaml"))
ACME = uuid4()


def _row(amount, merchant_id=None, probabilities=None, subscription=False):
    return ReviewRow(
        id=uuid4(), booked_at=date(2026, 7, 1), amount=Decimal(amount),
        description_raw="PAGO | ACME", account_name="bbva ····0001",
        merchant_id=merchant_id, merchant_name="ACME" if merchant_id else None,
        category_slug=max(probabilities, key=probabilities.get) if probabilities else None,
        category_confidence=max(probabilities.values()) if probabilities else None,
        category_probabilities=probabilities, is_subscription=subscription,
    )


def test_rows_of_a_merchant_become_one_item_with_a_summed_suggestion():
    rows = [
        _row("-10", ACME, {"groceries": 0.6, "restaurants_bars": 0.4}),
        _row("-20", ACME, {"groceries": 0.8, "restaurants_bars": 0.2}),
        _row("-500", None, {"payments_to_people": 0.7, "uncategorized_expense": 0.3}),
    ]
    items = build_review_items(rows, {}, TAXONOMY)
    assert [item.kind for item in items] == ["transaction", "merchant"]  # largest total first
    merchant = items[1]
    assert (merchant.count, merchant.total) == (2, Decimal("-30"))
    assert merchant.suggestion.category_slug == "groceries"
    assert merchant.suggestion.level1 == "shopping"
    assert abs(merchant.suggestion.confidence - 0.7) < 1e-9
    assert [s.slug for s in merchant.suggestion.top] == ["groceries", "restaurants_bars"]


def test_merge_suggestion_is_attached_to_its_merchant():
    merge = MergeSuggestion(merchant_id=uuid4(), name="ACME FOODS", confidence=0.6)
    [item] = build_review_items([_row("-10", ACME, {"groceries": 1.0})], {ACME: merge}, TAXONOMY)
    assert item.merge == merge


def test_subscription_is_suggested_when_any_row_is_flagged():
    rows = [_row("-9.99", ACME, {"entertainment": 0.9, "software_ai": 0.1}, subscription=True),
            _row("-9.99", ACME, {"entertainment": 0.9, "software_ai": 0.1})]
    assert build_review_items(rows, {}, TAXONOMY)[0].suggestion.is_subscription
```

Append to `apps/api/tests/test_api.py`:

```python
def test_label_rejects_a_missing_category():
    response = client.post(
        "/transactions/00000000-0000-0000-0000-000000000001/label", json={"is_subscription": True}
    )
    assert response.status_code == 422


def test_openapi_exposes_review_schemas():
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert {"ReviewItem", "ReviewCount", "CategoryOut", "MerchantOut", "ConfirmMerchant"} <= set(
        schemas
    )
```

- [ ] **Step 2: Write the failing integration test**

```python
# apps/api/tests/test_review_api.py
import pytest
from fastapi.testclient import TestClient

from finance.api.deps import db
from finance.api.main import app

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


def test_a_labelled_transaction_leaves_the_review_queue(client, db_conn, make_tx):
    tx = make_tx("-4321.07", "ZZTEST UNKNOWN CODE", merchant="ZZTEST UNKNOWN CODE")
    db_conn.execute(
        "update transactions set needs_review = true, category_source = 'jev',"
        " category_slug = 'uncategorized_expense' where id = %s", (tx,),
    )
    keys = {item["key"] for item in client.get("/review").json()}
    assert f"t:{tx}" in keys

    response = client.post(f"/transactions/{tx}/label",
                           json={"category_slug": "taxes", "is_subscription": False})
    assert response.status_code == 204
    assert f"t:{tx}" not in {item["key"] for item in client.get("/review").json()}


def test_unknown_category_and_unknown_merchant(client):
    missing = "00000000-0000-0000-0000-000000000009"
    bad = client.post(f"/merchants/{missing}/review",
                      json={"category_slug": "nope", "is_subscription": False})
    assert bad.status_code == 422
    gone = client.post(f"/merchants/{missing}/review",
                       json={"category_slug": "groceries", "is_subscription": False})
    assert gone.status_code == 404


def test_categories_and_merchant_autocomplete(client, db_conn):
    db_conn.execute("insert into merchants (name, match_key) values ('ZZTEST ACME', 'ZZTESTACME')")
    assert len(client.get("/categories").json()) == 55
    names = [m["name"] for m in client.get("/merchants", params={"q": "zztest"}).json()]
    assert names == ["ZZTEST ACME"]
```

- [ ] **Step 3: Run to verify failure**

Run: `cd apps/api && uv run pytest tests/test_review_queue.py tests/test_api.py -v`
Expected: FAIL (module missing, 404 on the new routes).

- [ ] **Step 4: Implement the pure queue**

```python
# apps/api/finance/categorization/review_queue.py
"""Group what needs review into one item per merchant (spec 11.1); rows without one stand alone."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from finance.categorization.taxonomy import Taxonomy


class ReviewRow(BaseModel):
    id: UUID
    booked_at: date
    amount: Decimal
    description_raw: str
    account_name: str
    merchant_id: UUID | None
    merchant_name: str | None
    category_slug: str | None
    category_confidence: float | None
    category_probabilities: dict[str, float] | None
    is_subscription: bool


class ReviewTransaction(BaseModel):
    id: UUID
    booked_at: date
    amount: Decimal
    description_raw: str
    account_name: str


class CategoryScore(BaseModel):
    slug: str
    confidence: float


class Suggestion(BaseModel):
    category_slug: str | None
    level1: str | None
    confidence: float | None
    is_subscription: bool
    top: list[CategoryScore]


class MergeSuggestion(BaseModel):
    merchant_id: UUID
    name: str
    confidence: float


class MerchantOut(BaseModel):
    id: UUID
    name: str


class ReviewItem(BaseModel):
    key: str
    kind: Literal["merchant", "transaction"]
    merchant: MerchantOut | None
    transactions: list[ReviewTransaction]
    count: int
    total: Decimal
    suggestion: Suggestion
    merge: MergeSuggestion | None


def suggestion_for(rows: list[ReviewRow], taxonomy: Taxonomy) -> Suggestion:
    """The category with the highest average probability across the merchant's rows."""
    scored = [row for row in rows if row.category_probabilities]
    totals: dict[str, float] = defaultdict(float)
    for row in scored:
        for slug, probability in row.category_probabilities.items():
            totals[slug] += probability
    top = [
        CategoryScore(slug=slug, confidence=total / len(scored))
        for slug, total in sorted(totals.items(), key=lambda kv: -kv[1])[:3]
    ]
    slug = top[0].slug if top else rows[0].category_slug
    confidence = top[0].confidence if top else rows[0].category_confidence
    return Suggestion(
        category_slug=slug,
        level1=taxonomy.get(slug).level1 if slug else None,
        confidence=confidence,
        is_subscription=any(row.is_subscription for row in rows),
        top=top,
    )


def build_review_items(
    rows: list[ReviewRow], merges: dict[UUID, MergeSuggestion], taxonomy: Taxonomy
) -> list[ReviewItem]:
    groups: dict[str, list[ReviewRow]] = defaultdict(list)
    for row in rows:
        groups[f"m:{row.merchant_id}" if row.merchant_id else f"t:{row.id}"].append(row)
    items = []
    for key, members in groups.items():
        first = members[0]
        merchant = MerchantOut(id=first.merchant_id, name=first.merchant_name) if first.merchant_id else None
        items.append(
            ReviewItem(
                key=key,
                kind="merchant" if merchant else "transaction",
                merchant=merchant,
                transactions=[ReviewTransaction.model_validate(m.model_dump()) for m in members],
                count=len(members),
                total=sum((m.amount for m in members), Decimal(0)),
                suggestion=suggestion_for(members, taxonomy),
                merge=merges.get(first.merchant_id) if first.merchant_id else None,
            )
        )
    return sorted(items, key=lambda item: (-abs(item.total), item.key))
```

- [ ] **Step 5: Implement the routes**

```python
# apps/api/finance/api/categories.py
"""The taxonomy for pickers, and the check every label request goes through."""

from fastapi import APIRouter, HTTPException
from psycopg import Connection
from pydantic import BaseModel

from finance.api.deps import Db

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryOut(BaseModel):
    slug: str
    tx_type: str
    level1: str


def require_category(conn: Connection, slug: str) -> None:
    if conn.execute("select 1 from categories where slug = %s", (slug,)).fetchone() is None:
        raise HTTPException(status_code=422, detail=f"Unknown category {slug!r}")


@router.get("")
def list_categories(conn: Db) -> list[CategoryOut]:
    rows = conn.execute(
        "select slug, tx_type, level1 from categories order by tx_type, level1, slug"
    ).fetchall()
    return [CategoryOut.model_validate(row) for row in rows]
```

```python
# apps/api/finance/api/review.py
"""The review inbox: one item per merchant, largest spend first."""

from fastapi import APIRouter
from psycopg import Connection
from pydantic import BaseModel

from finance.api.deps import Db
from finance.categorization.review_queue import (
    MergeSuggestion,
    ReviewItem,
    ReviewRow,
    build_review_items,
)
from finance.categorization.taxonomy import load_taxonomy

router = APIRouter(prefix="/review", tags=["review"])

_ROWS = """
select t.id, t.booked_at, t.amount, t.description_raw, a.name as account_name, t.merchant_id,
       m.name as merchant_name, t.category_slug, t.category_confidence, t.category_probabilities,
       t.is_subscription
from transactions t
join accounts a on a.id = t.account_id
left join merchants m on m.id = t.merchant_id
where t.category_source <> 'user'
  and (t.needs_review or (m.merge_candidate_id is not null and not m.confirmed))
order by t.booked_at, t.id
"""

_MERGES = """
select m.id, c.id as merchant_id, c.name, m.merge_confidence as confidence
from merchants m join merchants c on c.id = m.merge_candidate_id
where not m.confirmed
"""


class ReviewCount(BaseModel):
    pending: int


def review_items(conn: Connection) -> list[ReviewItem]:
    rows = [ReviewRow.model_validate(row) for row in conn.execute(_ROWS).fetchall()]
    merges = {row["id"]: MergeSuggestion.model_validate(row) for row in conn.execute(_MERGES)}
    return build_review_items(rows, merges, load_taxonomy(conn))


@router.get("")
def get_review(conn: Db) -> list[ReviewItem]:
    return review_items(conn)


@router.get("/count")
def get_review_count(conn: Db) -> ReviewCount:
    return ReviewCount(pending=len(review_items(conn)))
```

```python
# apps/api/finance/api/merchants.py
"""Merchant autocomplete and the merchant-level review actions."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from finance.api.categories import require_category
from finance.api.deps import Db
from finance.categorization.labels import NotFound, confirm_merchant, dismiss_merge, merge_merchants
from finance.categorization.review_queue import MerchantOut

router = APIRouter(prefix="/merchants", tags=["merchants"])


class ConfirmMerchant(BaseModel):
    category_slug: str
    is_subscription: bool
    name: str | None = None
    merge_into_id: UUID | None = None


class MergeRequest(BaseModel):
    into_id: UUID


@router.get("")
def list_merchants(
    conn: Db, q: str | None = None, limit: int = Query(default=20, ge=1, le=5000)
) -> list[MerchantOut]:
    rows = conn.execute(
        "select id, name from merchants where %(q)s::text is null or name ilike %(pattern)s"
        " order by name limit %(limit)s",
        {"q": q, "pattern": f"%{q}%", "limit": limit},
    ).fetchall()
    return [MerchantOut.model_validate(row) for row in rows]


@router.post("/{merchant_id}/review", status_code=204)
def review_merchant(merchant_id: UUID, body: ConfirmMerchant, conn: Db) -> Response:
    require_category(conn, body.category_slug)
    try:
        confirm_merchant(conn, merchant_id, body.category_slug, body.is_subscription,
                         body.name, body.merge_into_id)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)


@router.post("/{merchant_id}/merge", status_code=204)
def merge(merchant_id: UUID, body: MergeRequest, conn: Db) -> Response:
    try:
        merge_merchants(conn, merchant_id, body.into_id)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)


@router.post("/{merchant_id}/dismiss-merge", status_code=204)
def dismiss(merchant_id: UUID, conn: Db) -> Response:
    try:
        dismiss_merge(conn, merchant_id)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)
```

Append to `apps/api/finance/api/transactions.py` (imports: `HTTPException`, `Response`, `Field`, `require_category`, `NotFound`, `label_transaction`):

```python
class LabelTransaction(BaseModel):
    category_slug: str
    is_subscription: bool = False
    merchant_id: UUID | None = None
    new_merchant_name: str | None = Field(default=None, min_length=1)


@router.post("/{transaction_id}/label", status_code=204)
def label(transaction_id: UUID, body: LabelTransaction, conn: Db) -> Response:
    require_category(conn, body.category_slug)
    try:
        label_transaction(conn, transaction_id, body.category_slug, body.is_subscription,
                          body.merchant_id, body.new_merchant_name)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)
```

Register `review`, `categories` and `merchants` routers in `apps/api/finance/api/main.py`. The connection from `Db` commits when the request ends (psycopg pool context), so no explicit commit is needed; check it once by reloading `/review` after a label in Step 6.

- [ ] **Step 6: Run everything**

Run: `cd apps/api && uv run task test && uv run task test-integration && uv run task lint`
Expected: PASS. Then `uv run task api` and `curl -s localhost:8000/review/count` → `{"pending": N}` with N > 0 after Task 10's real run.

- [ ] **Step 7: Commit**

```bash
git add apps/api/finance/categorization/review_queue.py apps/api/finance/api apps/api/tests/test_review_queue.py apps/api/tests/test_api.py apps/api/tests/test_review_api.py
git commit -m "feat: serve the review queue by merchant and the label, confirm and merge actions"
```

### Task 13: The `/review` page

**Files:**
- Create (shadcn CLI): `apps/web/src/components/ui/{combobox,switch,progress,sonner}.tsx` and their dependencies
- Create: `apps/web/src/app/review/page.tsx`, `review-list.tsx`, `review-row.tsx`, `category-picker.tsx`, `merchant-picker.tsx`
- Modify: `apps/web/src/lib/api.ts`, `apps/web/src/app/layout.tsx`, `apps/web/src/lib/api-types.ts` (generated)

**Interfaces:**
- Consumes: the Task 12 routes through `Schemas["ReviewItem"]`, `Schemas["CategoryOut"]`, `Schemas["MerchantOut"]`, `Schemas["CategoryScore"]`, `Schemas["ReviewCount"]`.
- Produces: `apiPost(path, body?, { keepalive? })`, `reviewCount(): Promise<number | null>` in `lib/api.ts`; the `/review` route; a "Review" nav link with a pending badge.

- [ ] **Step 1: Add components and regenerate API types**

Run (API running on :8000):

```bash
cd apps/web
npx shadcn@latest add combobox switch progress sonner
npm run gen:api
```

Expected: the four components under `src/components/ui/` (plus `input-group` pulled in by combobox); `api-types.ts` contains `ReviewItem`. Check with `context7` the shadcn base-nova combobox examples ("groups", controlled `value`/`onValueChange`, `inputValue`/`onInputValueChange`, `itemToStringLabel`, `isItemEqualToValue`) and adapt prop names below if the generated component differs.

- [ ] **Step 2: API helpers**

Append to `apps/web/src/lib/api.ts`:

```ts
export async function apiPost(
  path: string,
  body?: unknown,
  init: { keepalive?: boolean } = {},
): Promise<void> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    keepalive: init.keepalive,
  });
  if (!response.ok) {
    throw new Error(`POST ${path} failed with ${response.status}`);
  }
}

/** Pending review items for the navigation badge; null when the API is unreachable. */
export async function reviewCount(): Promise<number | null> {
  try {
    return (await apiGet<Schemas["ReviewCount"]>("/review/count")).pending;
  } catch {
    return null;
  }
}
```

- [ ] **Step 3: Navigation badge and toaster**

In `apps/web/src/app/layout.tsx`: make `RootLayout` `async`, import `Badge`, `Toaster` (from `@/components/ui/sonner`) and `reviewCount`, then:

```tsx
export default async function RootLayout({ children }: LayoutProps<"/">) {
  const pending = await reviewCount();
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <header className="border-b">
          <nav className="mx-auto flex max-w-5xl gap-6 p-4 text-sm font-medium">
            <Link href="/imports">Imports</Link>
            <Link href="/transactions">Transactions</Link>
            <Link href="/review" className="flex items-center gap-2">
              Review
              {pending ? <Badge variant="secondary" className="tabular-nums">{pending}</Badge> : null}
            </Link>
          </nav>
        </header>
        {children}
        <Toaster position="bottom-center" />
      </body>
    </html>
  );
}
```

- [ ] **Step 4: Pickers**

```tsx
// apps/web/src/app/review/category-picker.tsx
"use client";

import {
  Combobox, ComboboxCollection, ComboboxContent, ComboboxEmpty, ComboboxGroup,
  ComboboxInput, ComboboxItem, ComboboxLabel, ComboboxList,
} from "@/components/ui/combobox";
import type { Schemas } from "@/lib/api";

type Category = Schemas["CategoryOut"];
type Group = { value: string; items: Category[] };

export const humanize = (slug: string) => slug.replaceAll("_", " ");

function byLevel1(categories: Category[]): Group[] {
  const groups = new Map<string, Category[]>();
  for (const category of categories) {
    groups.set(category.level1, [...(groups.get(category.level1) ?? []), category]);
  }
  return [...groups].map(([value, items]) => ({ value, items }));
}

type Props = {
  categories: Category[];
  suggested: Schemas["CategoryScore"][];
  value: string;
  onChange: (slug: string) => void;
};

export function CategoryPicker({ categories, suggested, value, onChange }: Props) {
  const bySlug = new Map(categories.map((c) => [c.slug, c]));
  const top = suggested.map((s) => bySlug.get(s.slug)).filter((c): c is Category => Boolean(c));
  const groups = [...(top.length ? [{ value: "suggested", items: top }] : []), ...byLevel1(categories)];

  return (
    <Combobox
      items={groups}
      value={bySlug.get(value) ?? null}
      onValueChange={(category: Category | null) => category && onChange(category.slug)}
      itemToStringLabel={(category: Category) => humanize(category.slug)}
    >
      <ComboboxInput placeholder="Category" className="w-full" />
      <ComboboxContent>
        <ComboboxEmpty>No category found.</ComboboxEmpty>
        <ComboboxList>
          {(group: Group) => (
            <ComboboxGroup key={group.value} items={group.items}>
              <ComboboxLabel>{humanize(group.value)}</ComboboxLabel>
              <ComboboxCollection>
                {(category: Category) => (
                  <ComboboxItem key={`${group.value}-${category.slug}`} value={category}>
                    {humanize(category.slug)}
                  </ComboboxItem>
                )}
              </ComboboxCollection>
            </ComboboxGroup>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
```

```tsx
// apps/web/src/app/review/merchant-picker.tsx
"use client";

import { useState } from "react";

import {
  Combobox, ComboboxContent, ComboboxEmpty, ComboboxInput, ComboboxItem, ComboboxList,
} from "@/components/ui/combobox";
import type { Schemas } from "@/lib/api";

/** An existing merchant (id) or a new name typed by the user (id null). */
export type MerchantChoice = { id: string | null; name: string };

type Props = {
  merchants: Schemas["MerchantOut"][];
  value: MerchantChoice | null;
  onChange: (merchant: MerchantChoice | null) => void;
};

export function MerchantPicker({ merchants, value, onChange }: Props) {
  const [query, setQuery] = useState(value?.name ?? "");
  const typed = query.trim();
  const exists = merchants.some((m) => m.name.toLowerCase() === typed.toLowerCase());
  const items: MerchantChoice[] = [
    ...merchants.map((m) => ({ id: m.id, name: m.name })),
    ...(typed && !exists ? [{ id: null, name: typed }] : []),
  ];

  return (
    <Combobox
      items={items}
      value={value}
      onValueChange={(merchant: MerchantChoice | null) => onChange(merchant)}
      inputValue={query}
      onInputValueChange={setQuery}
      itemToStringLabel={(merchant: MerchantChoice) => merchant.name}
      isItemEqualToValue={(a: MerchantChoice, b: MerchantChoice) => a.id === b.id && a.name === b.name}
    >
      <ComboboxInput placeholder="Merchant" className="w-full" />
      <ComboboxContent>
        <ComboboxEmpty>No merchant found.</ComboboxEmpty>
        <ComboboxList>
          {(merchant: MerchantChoice) => (
            <ComboboxItem key={merchant.id ?? `new-${merchant.name}`} value={merchant}>
              {merchant.id ? merchant.name : `Create "${merchant.name}"`}
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
```

- [ ] **Step 5: Row**

```tsx
// apps/web/src/app/review/review-row.tsx
"use client";

import { Check, ChevronRight } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { euro, type Schemas } from "@/lib/api";
import { cn } from "@/lib/utils";

import { CategoryPicker } from "./category-picker";
import { MerchantPicker, type MerchantChoice } from "./merchant-picker";

type Item = Schemas["ReviewItem"];
type Transaction = Schemas["ReviewTransaction"];

export type Decision = { categorySlug: string; isSubscription: boolean; merchant: MerchantChoice | null };

type Props = {
  item: Item;
  categories: Schemas["CategoryOut"][];
  merchants: Schemas["MerchantOut"][];
  onConfirm: (decision: Decision) => void;
  onLabelOne: (tx: Transaction, decision: Decision) => void;
  onMerge: () => void;
  onDismissMerge: () => void;
};

export function ReviewRow({ item, categories, merchants, onConfirm, onLabelOne, onMerge, onDismissMerge }: Props) {
  const { suggestion } = item;
  const [categorySlug, setCategorySlug] = useState(suggestion.category_slug ?? "");
  const [isSubscription, setIsSubscription] = useState(suggestion.is_subscription);
  const [merchant, setMerchant] = useState<MerchantChoice | null>(item.merchant ?? null);
  const [open, setOpen] = useState(false);
  const level1 = categories.find((c) => c.slug === categorySlug)?.level1;
  const showConfidence = categorySlug === suggestion.category_slug && suggestion.confidence != null;

  return (
    <li className="flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        disabled={item.count < 2}
        className="flex min-w-0 items-center gap-2 text-left text-sm text-muted-foreground"
      >
        <ChevronRight className={cn("size-4 shrink-0 transition-transform", open && "rotate-90", item.count < 2 && "invisible")} />
        <span className="truncate">{item.transactions[0].description_raw}</span>
        {item.count > 1 && <span className="shrink-0 tabular-nums">×{item.count}</span>}
        <span className="ml-auto shrink-0 font-medium tabular-nums text-foreground">{euro.format(Number(item.total))}</span>
      </button>

      <div className="grid gap-3 md:grid-cols-[1fr_1fr_7rem_auto_auto] md:items-center">
        <MerchantPicker merchants={merchants} value={merchant} onChange={setMerchant} />
        <div className="flex items-center gap-2">
          <CategoryPicker categories={categories} suggested={suggestion.top} value={categorySlug} onChange={setCategorySlug} />
          {showConfidence && (
            <span className="text-xs tabular-nums text-muted-foreground" title="jev confidence">
              ·{Math.round((suggestion.confidence ?? 0) * 100)}
            </span>
          )}
        </div>
        <span className="truncate text-sm text-muted-foreground">{level1 ?? "—"}</span>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <Switch checked={isSubscription} onCheckedChange={(checked) => setIsSubscription(checked)} />
          Subscription
        </label>
        <Button size="icon" aria-label="Confirm" disabled={!categorySlug}
                onClick={() => onConfirm({ categorySlug, isSubscription, merchant })}>
          <Check />
        </Button>
      </div>

      {item.merge && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm">
          <span>Same merchant as <strong>{item.merge.name}</strong>?</span>
          <Button size="sm" variant="secondary" className="ml-auto" onClick={onMerge}>Merge</Button>
          <Button size="sm" variant="ghost" onClick={onDismissMerge}>No</Button>
        </div>
      )}

      {open && (
        <ul className="flex flex-col divide-y border-t">
          {item.transactions.map((tx) => (
            <TransactionLine key={tx.id} tx={tx} categories={categories} initial={categorySlug}
                             onLabel={(decision) => onLabelOne(tx, decision)} />
          ))}
        </ul>
      )}
    </li>
  );
}

function TransactionLine({ tx, categories, initial, onLabel }: {
  tx: Transaction;
  categories: Schemas["CategoryOut"][];
  initial: string;
  onLabel: (decision: Decision) => void;
}) {
  const [slug, setSlug] = useState(initial);
  const [subscription, setSubscription] = useState(false);
  return (
    <li className="grid gap-2 py-2 text-sm md:grid-cols-[6rem_1fr_1fr_auto_auto] md:items-center">
      <span className="tabular-nums text-muted-foreground">{tx.booked_at}</span>
      <span className="truncate">{euro.format(Number(tx.amount))} · {tx.account_name}</span>
      <CategoryPicker categories={categories} suggested={[]} value={slug} onChange={setSlug} />
      <Switch checked={subscription} onCheckedChange={(checked) => setSubscription(checked)} aria-label="Subscription" />
      <Button size="icon" variant="outline" aria-label="Confirm this transaction" disabled={!slug}
              onClick={() => onLabel({ categorySlug: slug, isSubscription: subscription, merchant: null })}>
        <Check />
      </Button>
    </li>
  );
}
```

- [ ] **Step 6: List with deferred saves and undo**

```tsx
// apps/web/src/app/review/review-list.tsx
"use client";

import { CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Progress } from "@/components/ui/progress";
import { apiPost, type Schemas } from "@/lib/api";

import { ReviewRow, type Decision } from "./review-row";

type Item = Schemas["ReviewItem"];
type Transaction = Schemas["ReviewTransaction"];
type Pending = { timer: ReturnType<typeof setTimeout>; commit: (keepalive: boolean) => void };

const UNDO_MS = 5000;
const byTotal = (a: Item, b: Item) => Math.abs(Number(b.total)) - Math.abs(Number(a.total));

type Props = {
  initialItems: Item[];
  categories: Schemas["CategoryOut"][];
  merchants: Schemas["MerchantOut"][];
};

export function ReviewList({ initialItems, categories, merchants }: Props) {
  const [items, setItems] = useState(initialItems);
  const [total] = useState(initialItems.length);
  const pending = useRef(new Map<string, Pending>());

  useEffect(() => {
    // Leaving the page sends what is still waiting for its undo window.
    const flush = () => pending.current.forEach(({ timer, commit }) => { clearTimeout(timer); commit(true); });
    window.addEventListener("pagehide", flush);
    return () => window.removeEventListener("pagehide", flush);
  }, []);

  function replace(key: string, next: Item | null) {
    setItems((current) => {
      const others = current.filter((item) => item.key !== key);
      return (next ? [...others, next] : others).sort(byTotal);
    });
  }

  function schedule(original: Item, next: Item | null, send: (keepalive: boolean) => Promise<void>) {
    replace(original.key, next);
    const id = `${original.key}:${crypto.randomUUID()}`;
    const commit = (keepalive: boolean) => {
      pending.current.delete(id);
      send(keepalive).catch(() => {
        toast.error("Could not save that change.");
        replace(original.key, original);
      });
    };
    const timer = setTimeout(() => commit(false), UNDO_MS);
    pending.current.set(id, { timer, commit });
    toast("Confirmed", {
      duration: UNDO_MS,
      action: {
        label: "Undo",
        onClick: () => { clearTimeout(timer); pending.current.delete(id); replace(original.key, original); },
      },
    });
  }

  function confirm(item: Item, d: Decision) {
    if (item.kind === "merchant" && item.merchant) {
      const merchantId = item.merchant.id;
      const body = {
        category_slug: d.categorySlug,
        is_subscription: d.isSubscription,
        name: d.merchant && d.merchant.id === null ? d.merchant.name : null,
        merge_into_id: d.merchant?.id && d.merchant.id !== merchantId ? d.merchant.id : null,
      };
      schedule(item, null, (keepalive) => apiPost(`/merchants/${merchantId}/review`, body, { keepalive }));
    } else {
      labelOne(item, item.transactions[0], d);
    }
  }

  function labelOne(item: Item, tx: Transaction, d: Decision) {
    const rest = item.transactions.filter((t) => t.id !== tx.id);
    const next = rest.length
      ? { ...item, transactions: rest, count: rest.length,
          total: String(rest.reduce((sum, t) => sum + Number(t.amount), 0)) }
      : null;
    const body = {
      category_slug: d.categorySlug,
      is_subscription: d.isSubscription,
      merchant_id: d.merchant?.id ?? null,
      new_merchant_name: d.merchant && d.merchant.id === null ? d.merchant.name : null,
    };
    schedule(item, next, (keepalive) => apiPost(`/transactions/${tx.id}/label`, body, { keepalive }));
  }

  const done = Math.max(total - items.length, 0);
  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between gap-4">
          <h1 className="text-xl font-semibold tracking-tight">Review</h1>
          {total > 0 && <span className="text-sm tabular-nums text-muted-foreground">{done} of {total}</span>}
        </div>
        <p className="text-sm text-muted-foreground">Confirm or fix. Your answer applies to every transaction of the merchant.</p>
        {total > 0 && <Progress value={(done / total) * 100} />}
      </header>

      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
          <CheckCircle2 className="size-8" />
          <p>All caught up</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {items.map((item) => (
            <ReviewRow
              key={item.key}
              item={item}
              categories={categories}
              merchants={merchants}
              onConfirm={(d) => confirm(item, d)}
              onLabelOne={(tx, d) => labelOne(item, tx, d)}
              onMerge={() => item.merge && item.merchant && schedule(item, null, (keepalive) =>
                apiPost(`/merchants/${item.merchant!.id}/merge`, { into_id: item.merge!.merchant_id }, { keepalive }))}
              onDismissMerge={() => item.merchant && schedule(item, { ...item, merge: null }, (keepalive) =>
                apiPost(`/merchants/${item.merchant!.id}/dismiss-merge`, undefined, { keepalive }))}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
```

- [ ] **Step 7: Page**

```tsx
// apps/web/src/app/review/page.tsx
import { apiGet, type Schemas } from "@/lib/api";

import { ReviewList } from "./review-list";

export const dynamic = "force-dynamic";

export default async function ReviewPage() {
  const [items, categories, merchants] = await Promise.all([
    apiGet<Schemas["ReviewItem"][]>("/review"),
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["MerchantOut"][]>("/merchants?limit=5000"),
  ]);
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-6">
      <ReviewList initialItems={items} categories={categories} merchants={merchants} />
    </main>
  );
}
```

- [ ] **Step 8: Static checks**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm run build`
Expected: no errors. Fix prop-name mismatches against the generated combobox if `tsc` reports them.

- [ ] **Step 9: Check the flow as a user with agent-browser core**

Run the API (`cd apps/api && uv run task api`) and the web (`cd apps/web && npm run dev`). Load `agent-browser skills get core`, use a named session on `http://localhost:3000`:
1. Snapshot `/review`: header "Review", "0 of N", rows with merchant, category, level 1, subscription, a small confidence number, no confidence column.
2. Change one category: level 1 text follows. Confirm: the row disappears, the toast shows Undo; click Undo: the row returns. Confirm again and wait 6 s: reload, the row stays gone.
3. Expand a merchant with ×2 or more and label one transaction alone.
4. Narrow the viewport to 390 px: rows stack as cards, nothing overflows.
5. Stop the API, reload `/imports`: the page renders without the badge (Review Focus). Restart the API.
Save screenshots with absolute paths under `dogfood-output/`, then `close` the session.

- [ ] **Step 10: Commit**

```bash
git add apps/web
git commit -m "feat: add the review inbox with merchant rows, pickers and undo"
```

### Task 14: `finance eval-categorization`

**Files:**
- Create: `apps/api/finance/evals/__init__.py` (empty), `metrics.py`, `report.py`, `run.py`
- Modify: `apps/api/finance/cli.py`, `.gitignore` (already has `eval-output/`; verify)
- Test: `apps/api/tests/test_eval_metrics.py`, `apps/api/tests/test_eval_run.py`

**Interfaces:**
- Consumes: `categorize`, `CategorizationContext`, `MerchantRoster`, `find_pairs`, `PairCandidate`, `load_taxonomy`, `load_rules`, `TypesafeJev`, `Jev`, `match_key`, `REPO_ROOT`.
- Produces: `EvalRow`, `Metrics` (with `level2`, `level1`, `subscription_precision`, `subscription_recall`, `merchant`), `compute_metrics(rows) -> Metrics`; `EvalMeta(run_at, model, fingerprint, note="", input_tokens=0)`, `render_markdown(meta, metrics) -> str`, `history_line(meta, metrics) -> str`; `async evaluate(conn, ctx, jev, limit=None) -> tuple[list[EvalRow], str]`; `run_eval(conn, settings, limit=None, note="", out_root=..., history=...) -> Path`; CLI `finance eval-categorization [--limit N] [--note TEXT]`.

- [ ] **Step 1: Write the failing metric tests**

```python
# apps/api/tests/test_eval_metrics.py
from datetime import datetime
from uuid import uuid4

from finance.evals.metrics import EvalRow, compute_metrics
from finance.evals.report import EvalMeta, history_line, render_markdown


def _row(golden, predicted, confidence, *, sub=None, flagged=False, merchant=None, named=None):
    level1 = {"groceries": "shopping", "fashion": "shopping", "restaurants_bars": "leisure"}
    return EvalRow(
        transaction_id=uuid4(), text="synthetic", outgoing=True,
        golden_slug=golden, golden_level1=level1[golden], golden_subscription=sub,
        golden_merchant=merchant, predicted_slug=predicted, predicted_level1=level1[predicted],
        confidence=confidence, level1_confidence=confidence, predicted_subscription=flagged,
        subscription_score=0.9 if flagged else 0.1, predicted_merchant=named,
    )


ROWS = [
    _row("groceries", "groceries", 0.99, sub=False, merchant="ACME", named="ACME"),
    _row("groceries", "fashion", 0.97, sub=False, merchant="ACME", named="ACME FOODS"),
    _row("restaurants_bars", "restaurants_bars", 0.6, sub=True, flagged=True),
    _row("fashion", "restaurants_bars", 0.4, sub=True),
]


def test_accuracy_buckets_and_thresholds():
    metrics = compute_metrics(ROWS)
    assert (metrics.level2.right, metrics.level2.total) == (2, 4)
    assert metrics.level1.right == 3  # fashion vs groceries is still shopping: right at level 1
    top = [b for b in metrics.level2.buckets if b.low == 0.95][0]
    assert (top.rows, top.right) == (2, 1)
    at_95 = [t for t in metrics.level2.thresholds if t.threshold == 0.95][0]
    assert (at_95.accepted, at_95.wrong, at_95.review) == (2, 1, 2)


def test_subscription_and_merchant_scores():
    metrics = compute_metrics(ROWS)
    assert (metrics.subscription_precision.hits, metrics.subscription_precision.total) == (1, 1)
    assert (metrics.subscription_recall.hits, metrics.subscription_recall.total) == (1, 2)
    assert (metrics.merchant.hits, metrics.merchant.total) == (1, 2)


def test_report_and_history_line():
    meta = EvalMeta(run_at=datetime(2026, 9, 24, 10, 0), model="jev-1.13.0",
                    fingerprint="abcd1234", note="synthetic")
    metrics = compute_metrics(ROWS)
    assert "| 0.95 | 2 | 1 |" in render_markdown(meta, metrics)
    line = history_line(meta, metrics)
    assert line.startswith("| 2026-09-24 | eval | jev-1.13.0 | 4 | 50.0% | 75.0% | 50.0% | 2 |")
    assert line.count("|") == 11
```

- [ ] **Step 2: Write the failing dry-run test**

```python
# apps/api/tests/test_eval_run.py
import asyncio

import pytest

from finance.categorization.categorizer import CategorizationContext
from finance.categorization.labels import confirm_merchant, label_transaction
from finance.categorization.rules import load_rules
from finance.categorization.taxonomy import load_taxonomy
from finance.evals.run import evaluate
from finance.settings import Settings
from tests.fakes import FakeJev, jev_result

pytestmark = pytest.mark.integration


def test_dry_run_scores_user_labels_without_merchant_defaults(db_conn, make_tx):
    tx = make_tx("-9.90", "PAGO | ZZTEST ACME", merchant="ZZTEST ACME")
    label_transaction(db_conn, tx, "restaurants_bars", False, new_merchant_name="ZZTEST ACME")
    merchant = db_conn.execute("select merchant_id from transactions where id = %s",
                               (tx,)).fetchone()["merchant_id"]
    confirm_merchant(db_conn, merchant, "restaurants_bars", False)
    before = db_conn.execute("select count(*) as n from transaction_labels").fetchone()["n"]

    jev = FakeJev(first={"ZZTEST ACME": jev_result(
        merchant={"ZZTEST ACME": 0.99, "none": 0.01},
        category={"groceries": 0.97, "restaurants_bars": 0.03})})
    ctx = CategorizationContext(load_taxonomy(db_conn), load_rules(db_conn), Settings())
    rows, model = asyncio.run(evaluate(db_conn, ctx, jev))

    mine = next(row for row in rows if row.transaction_id == tx)
    assert (mine.golden_slug, mine.predicted_slug) == ("restaurants_bars", "groceries")
    assert model == "jev-test"
    after = db_conn.execute("select count(*) as n from transaction_labels").fetchone()["n"]
    assert after == before  # a dry run writes nothing
```

- [ ] **Step 3: Run to verify failure**

Run: `cd apps/api && uv run pytest tests/test_eval_metrics.py -v`
Expected: FAIL (module missing).

- [ ] **Step 4: Implement metrics and report**

```python
# apps/api/finance/evals/metrics.py
"""Benchmark metrics over (golden, predicted) rows; a pure function (spec 13.1)."""

from uuid import UUID

from pydantic import BaseModel

from finance.categorization.jev_questions import match_key

BUCKETS = ((0.0, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 0.95), (0.95, 1.01))
THRESHOLDS = (0.8, 0.85, 0.9, 0.95)


class EvalRow(BaseModel):
    transaction_id: UUID
    text: str
    outgoing: bool
    golden_slug: str
    golden_level1: str
    golden_subscription: bool | None = None
    golden_merchant: str | None = None
    predicted_slug: str
    predicted_level1: str
    confidence: float | None
    level1_confidence: float | None
    predicted_subscription: bool
    subscription_score: float | None
    predicted_merchant: str | None


class Bucket(BaseModel):
    low: float
    high: float
    rows: int
    right: int


class ThresholdResult(BaseModel):
    threshold: float
    accepted: int
    wrong: int
    review: int

    def precision(self) -> float | None:
        return 1 - self.wrong / self.accepted if self.accepted else None


class LevelMetrics(BaseModel):
    right: int
    total: int
    buckets: list[Bucket]
    thresholds: list[ThresholdResult]

    def accuracy(self) -> float:
        return self.right / self.total if self.total else 0.0

    def at(self, threshold: float) -> ThresholdResult:
        return next(t for t in self.thresholds if t.threshold == threshold)


class Ratio(BaseModel):
    hits: int
    total: int


class Metrics(BaseModel):
    rows: int
    level2: LevelMetrics
    level1: LevelMetrics
    subscription_precision: Ratio
    subscription_recall: Ratio
    merchant: Ratio


def _level(scored: list[tuple[bool, float]]) -> LevelMetrics:
    buckets = []
    for low, high in BUCKETS:
        inside = [right for right, confidence in scored if low <= confidence < high]
        buckets.append(Bucket(low=low, high=high, rows=len(inside), right=sum(inside)))
    thresholds = []
    for threshold in THRESHOLDS:
        accepted = [right for right, confidence in scored if confidence >= threshold]
        thresholds.append(ThresholdResult(
            threshold=threshold, accepted=len(accepted), wrong=accepted.count(False),
            review=len(scored) - len(accepted),
        ))
    return LevelMetrics(right=sum(r for r, _ in scored), total=len(scored), buckets=buckets,
                        thresholds=thresholds)


def compute_metrics(rows: list[EvalRow]) -> Metrics:
    level2 = _level([(r.predicted_slug == r.golden_slug, r.confidence or 0.0) for r in rows])
    level1 = _level([(r.predicted_level1 == r.golden_level1, r.level1_confidence or 0.0) for r in rows])
    labelled = [r for r in rows if r.golden_subscription is not None]
    flagged = [r for r in labelled if r.outgoing and r.predicted_subscription]
    truly = [r for r in labelled if r.golden_subscription]
    named = [r for r in rows if r.golden_merchant]
    return Metrics(
        rows=len(rows),
        level2=level2,
        level1=level1,
        subscription_precision=Ratio(hits=sum(r.golden_subscription for r in flagged), total=len(flagged)),
        subscription_recall=Ratio(hits=sum(r.predicted_subscription and r.outgoing for r in truly),
                                  total=len(truly)),
        merchant=Ratio(
            hits=sum(bool(r.predicted_merchant)
                     and match_key(r.predicted_merchant) == match_key(r.golden_merchant) for r in named),
            total=len(named),
        ),
    )
```

```python
# apps/api/finance/evals/report.py
"""Readable outputs of a benchmark run: report.md and one line of docs/evals/HISTORY.md."""

from datetime import datetime

from pydantic import BaseModel

from finance.evals.metrics import LevelMetrics, Metrics

ACCEPT = 0.95


class EvalMeta(BaseModel):
    run_at: datetime
    model: str
    fingerprint: str
    note: str = ""
    input_tokens: int = 0


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1%}"


def _level_tables(name: str, level: LevelMetrics) -> list[str]:
    lines = [f"## {name}: {level.right}/{level.total} = {_pct(level.accuracy())}", "",
             "| Confidence | Rows | Right |", "|---|---|---|"]
    for b in level.buckets:
        right = _pct(b.right / b.rows) if b.rows else "—"
        lines.append(f"| {b.low:.2f}–{min(b.high, 1):.2f} | {b.rows} | {right} |")
    lines += ["", "| Threshold | Accepted | Wrong | Precision | Review |", "|---|---|---|---|---|"]
    for t in level.thresholds:
        lines.append(f"| {t.threshold:.2f} | {t.accepted} | {t.wrong} | {_pct(t.precision())} | {t.review} |")
    return lines + [""]


def render_markdown(meta: EvalMeta, metrics: Metrics) -> str:
    cost = meta.input_tokens * 0.042 / 1_000_000
    lines = [
        f"# Categorization eval {meta.run_at:%Y-%m-%d %H:%M}",
        "",
        f"jev `{meta.model}` · taxonomy and rules `{meta.fingerprint}` · {metrics.rows} golden rows"
        f" · about ${cost:.3f}" + (f" · {meta.note}" if meta.note else ""),
        "",
        "jev varies by about ten rows between identical runs; smaller differences are noise.",
        "",
    ]
    lines += _level_tables("Level 2", metrics.level2) + _level_tables("Level 1", metrics.level1)
    sp, sr, m = metrics.subscription_precision, metrics.subscription_recall, metrics.merchant
    lines += [
        "## Subscriptions and merchants", "",
        f"- Subscription precision {sp.hits}/{sp.total}, recall {sr.hits}/{sr.total} (noul > 0.7, expenses)",
        f"- Merchant name right {m.hits}/{m.total} (same match key)",
        "",
    ]
    return "\n".join(lines)


def history_line(meta: EvalMeta, metrics: Metrics) -> str:
    at = metrics.level2.at(ACCEPT)
    sp, sr = metrics.subscription_precision, metrics.subscription_recall
    cells = [
        f"{meta.run_at:%Y-%m-%d}", "eval", meta.model, str(metrics.rows),
        _pct(metrics.level2.accuracy()), _pct(metrics.level1.accuracy()),
        _pct(at.precision()), str(at.review), f"{sp.hits}/{sp.total} · {sr.hits}/{sr.total}",
        meta.note,
    ]
    return "| " + " | ".join(cells) + " |"
```

- [ ] **Step 5: Implement the dry run and the command**

```python
# apps/api/finance/evals/run.py
"""Dry run of the production categorizer against the user's labels (spec 13.1)."""

import asyncio
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from psycopg import Connection

from finance.categorization.categorizer import CategorizationContext, categorize
from finance.categorization.jev_client import Jev, TypesafeJev
from finance.categorization.merchants import MerchantRoster
from finance.categorization.models import TxInput
from finance.categorization.pairing import PairCandidate, find_pairs
from finance.categorization.rules import load_rules
from finance.categorization.taxonomy import load_taxonomy
from finance.evals.metrics import EvalRow, compute_metrics
from finance.evals.report import EvalMeta, history_line, render_markdown
from finance.settings import REPO_ROOT, Settings

_GOLDEN = """
select distinct on (l.transaction_id) l.transaction_id as id, l.category_slug, l.is_subscription,
       m.name as golden_merchant, a.bank, t.booked_at, t.amount, t.description_raw,
       t.bank_concept, t.merchant
from transaction_labels l
join transactions t on t.id = l.transaction_id
join accounts a on a.id = t.account_id
left join merchants m on m.id = l.merchant_id
where l.source = 'user'
order by l.transaction_id, l.labeled_at desc
"""


def fingerprint(ctx: CategorizationContext) -> str:
    payload = json.dumps(
        [c.model_dump() for c in sorted(ctx.taxonomy.categories(), key=lambda c: c.slug)]
        + [r.model_dump() for r in ctx.rules],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:8]


async def evaluate(
    conn: Connection, ctx: CategorizationContext, jev: Jev, limit: int | None = None
) -> tuple[list[EvalRow], str]:
    golden = conn.execute(_GOLDEN).fetchall()[:limit]
    everything = conn.execute(
        "select id, account_id, booked_at, amount, description_raw from transactions"
    ).fetchall()
    pairs = find_pairs([PairCandidate.model_validate(r) for r in everything],
                       ctx.settings.transfer_pattern, ctx.settings.transfer_window_days)
    pair_of = {}
    for out_id, in_id in pairs:
        pair_of[out_id] = pair_of[in_id] = uuid4()
    rows = [TxInput.model_validate(g | {"transfer_pair_id": pair_of.get(g["id"])}) for g in golden]
    # No merchant defaults and an empty roster: they come from the labels being scored.
    results = await categorize(rows, ctx, jev, MerchantRoster([]), use_merchant_defaults=False)
    taxonomy = ctx.taxonomy
    scored = [
        EvalRow(
            transaction_id=g["id"],
            text=(f"{g['bank_concept']} | " if g["bank_concept"] else "") + (g["merchant"] or ""),
            outgoing=g["amount"] < 0,
            golden_slug=g["category_slug"],
            golden_level1=taxonomy.get(g["category_slug"]).level1,
            golden_subscription=g["is_subscription"],
            golden_merchant=g["golden_merchant"],
            predicted_slug=r.category_slug,
            predicted_level1=taxonomy.get(r.category_slug).level1,
            confidence=r.category_confidence,
            level1_confidence=r.level1_confidence,
            predicted_subscription=r.is_subscription,
            subscription_score=r.subscription_score,
            predicted_merchant=r.merchant_name,
        )
        for g, r in zip(golden, results, strict=True)
    ]
    model = next((r.model for r in results if r.model), "no jev call")
    return scored, model


def run_eval(
    conn: Connection,
    settings: Settings,
    limit: int | None = None,
    note: str = "",
    out_root: Path = REPO_ROOT / "eval-output",
    history: Path = REPO_ROOT / "docs" / "evals" / "HISTORY.md",
) -> Path:
    if not settings.typesafe_api_key:
        raise RuntimeError("TYPESAFE_API_KEY is not set")
    ctx = CategorizationContext(load_taxonomy(conn), load_rules(conn), settings)

    async def _run():
        async with TypesafeJev(settings.typesafe_api_key, settings.jev_concurrency,
                               tags=["eval"]) as jev:
            rows, model = await evaluate(conn, ctx, jev, limit)
            return rows, model, jev.input_tokens

    rows, model, tokens = asyncio.run(_run())
    metrics = compute_metrics(rows)
    meta = EvalMeta(run_at=datetime.now(), model=model, fingerprint=fingerprint(ctx), note=note,
                    input_tokens=tokens)
    out = out_root / f"{meta.run_at:%Y%m%d-%H%M%S}"
    out.mkdir(parents=True)
    with (out / "rows.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(EvalRow.model_fields))
        writer.writeheader()
        writer.writerows(row.model_dump() for row in rows)
    summary = {"meta": meta.model_dump(mode="json"), "metrics": metrics.model_dump()}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    (out / "report.md").write_text(render_markdown(meta, metrics))
    with history.open("a") as handle:
        handle.write(history_line(meta, metrics) + "\n")
    return out
```

Add to `apps/api/finance/cli.py`:

```python
from finance.evals.run import run_eval
from finance.settings import get_settings


@app.command("eval-categorization")
def eval_command(
    limit: int | None = typer.Option(None, help="Only the first N labelled transactions."),
    note: str = typer.Option("", help="What changed, for docs/evals/HISTORY.md."),
) -> None:
    """Benchmark the categorizer against your labels (dry run, writes nothing to the database)."""
    with connection() as conn:
        out = run_eval(conn, get_settings(), limit=limit, note=note)
    typer.echo((out / "report.md").read_text())
    typer.echo(f"saved to {out}")
```

- [ ] **Step 6: Run tests and lint**

Run: `cd apps/api && uv run task test && uv run pytest tests/test_eval_run.py -m integration -v && uv run task lint`
Expected: PASS. (The real benchmark runs in Task 15, once the golden set is loaded.)

- [ ] **Step 7: Commit**

```bash
git add apps/api/finance/evals apps/api/finance/cli.py apps/api/tests/test_eval_metrics.py apps/api/tests/test_eval_run.py
git commit -m "feat: benchmark the categorizer against user labels with a readable history"
```

### Task 15: Labels export/import, first golden set, dogfood, docs

**Files:**
- Create: `apps/api/finance/evals/labels_io.py`
- Modify: `apps/api/finance/cli.py`, `README.md`, `CLAUDE.md`, `docs/superpowers/spikes/2026-09-23-jev-categorization/README.md`, `docs/evals/HISTORY.md` (appended by the command)
- Test: `apps/api/tests/test_labels_io.py`

**Interfaces:**
- Consumes: `label_transaction`, `REPO_ROOT`.
- Produces: `FIELDS = ("dedup_key", "category_slug", "is_subscription", "merchant")`; `export_labels(conn, path) -> int`; `LabelsImport(imported: int, missing: int)`; `import_labels(conn, path) -> LabelsImport`; CLI `finance labels export [PATH]` (default `data/labels/labels-YYYYMMDD.csv`) and `finance labels import PATH`.

- [ ] **Step 1: Write the failing round-trip test**

```python
# apps/api/tests/test_labels_io.py
import csv

import pytest

from finance.categorization.labels import label_transaction
from finance.evals.labels_io import FIELDS, export_labels, import_labels

pytestmark = pytest.mark.integration


def test_labels_travel_by_dedup_key(db_conn, make_tx, tmp_path):
    labelled = make_tx("-9.90", "PAGO | ZZTEST ACME", merchant="ZZTEST ACME")
    label_transaction(db_conn, labelled, "groceries", False, new_merchant_name="ZZTEST ACME")
    exported = tmp_path / "labels.csv"
    assert export_labels(db_conn, exported) >= 1
    key = db_conn.execute("select dedup_key from transactions where id = %s",
                          (labelled,)).fetchone()["dedup_key"]
    rows = {row["dedup_key"]: row for row in csv.DictReader(exported.open())}
    assert rows[key]["category_slug"] == "groceries" and rows[key]["merchant"] == "ZZTEST ACME"

    fresh = make_tx("-4.00", "PAGO | ZZTEST TOBACCO", merchant="ZZTEST TOBACCO")
    fresh_key = db_conn.execute("select dedup_key from transactions where id = %s",
                                (fresh,)).fetchone()["dedup_key"]
    incoming = tmp_path / "incoming.csv"
    with incoming.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow({"dedup_key": fresh_key, "category_slug": "tobacco",
                         "is_subscription": "false", "merchant": "ZZTEST TOBACCO"})
        writer.writerow({"dedup_key": "missing", "category_slug": "tobacco",
                         "is_subscription": "false", "merchant": ""})
    result = import_labels(db_conn, incoming)
    assert (result.imported, result.missing) == (1, 1)
    row = db_conn.execute("select category_slug, category_source from transactions where id = %s",
                          (fresh,)).fetchone()
    assert (row["category_slug"], row["category_source"]) == ("tobacco", "user")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/api && uv run pytest tests/test_labels_io.py -m integration -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# apps/api/finance/evals/labels_io.py
"""User labels as CSV keyed by dedup_key, so the golden set survives database resets."""

import csv
from pathlib import Path

from psycopg import Connection
from pydantic import BaseModel

from finance.categorization.labels import label_transaction

FIELDS = ("dedup_key", "category_slug", "is_subscription", "merchant")

_EXPORT = """
select distinct on (l.transaction_id) t.dedup_key, l.category_slug, l.is_subscription,
       coalesce(m.name, '') as merchant
from transaction_labels l
join transactions t on t.id = l.transaction_id
left join merchants m on m.id = l.merchant_id
where l.source = 'user'
order by l.transaction_id, l.labeled_at desc
"""


class LabelsImport(BaseModel):
    imported: int
    missing: int


def export_labels(conn: Connection, path: Path) -> int:
    rows = conn.execute(_EXPORT).fetchall()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def import_labels(conn: Connection, path: Path) -> LabelsImport:
    imported = missing = 0
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            found = conn.execute(
                "select id from transactions where dedup_key = %s", (row["dedup_key"],)
            ).fetchone()
            if found is None:
                missing += 1
                continue
            label_transaction(
                conn,
                found["id"],
                row["category_slug"],
                row["is_subscription"].strip().lower() in ("1", "true"),
                new_merchant_name=row["merchant"] or None,
            )
            imported += 1
    return LabelsImport(imported=imported, missing=missing)
```

Add to `apps/api/finance/cli.py`:

```python
from datetime import date

from finance.evals.labels_io import export_labels, import_labels
from finance.settings import REPO_ROOT

labels_app = typer.Typer(help="Export or import your labels (the golden set).", no_args_is_help=True)
app.add_typer(labels_app, name="labels")


@labels_app.command("export")
def labels_export(path: Path | None = typer.Argument(None)) -> None:
    """Write your labels to CSV (default: data/labels/labels-YYYYMMDD.csv)."""
    target = path or REPO_ROOT / "data" / "labels" / f"labels-{date.today():%Y%m%d}.csv"
    with connection() as conn:
        count = export_labels(conn, target)
    typer.echo(f"exported={count} to {target}")


@labels_app.command("import")
def labels_import(path: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    """Load labels from CSV by dedup_key."""
    with connection() as conn:
        result = import_labels(conn, path)
    typer.echo(f"imported={result.imported} missing={result.missing}")
```

- [ ] **Step 4: Run tests and lint, then commit the code**

Run: `cd apps/api && uv run task test && uv run task test-integration && uv run task lint`
Expected: PASS.

```bash
git add apps/api/finance/evals/labels_io.py apps/api/finance/cli.py apps/api/tests/test_labels_io.py
git commit -m "feat: export and import labels by dedup key"
```

- [ ] **Step 5: Dogfood the whole slice before loading the golden set**

With the real ledger categorized (Task 10) and API + web running, load `agent-browser skills get dogfood` and run one pass over `/imports`, `/transactions` and `/review`; write the report to `dogfood-output/`. While dogfooding `/review`, only confirm rows whose suggestion is right, or press Undo: every confirm sets a real merchant default. Fix any blocker found (its own `fix:` commit) before continuing.

- [ ] **Step 6: Load the spike golden set as the first user labels**

```bash
mkdir -p data/labels
python3 - <<'EOF'
import csv
source = "docs/superpowers/spikes/2026-09-23-jev-categorization/output/golden.csv"
with open(source) as src, open("data/labels/golden-spike.csv", "w", newline="") as dst:
    writer = csv.DictWriter(dst, fieldnames=["dedup_key", "category_slug", "is_subscription", "merchant"])
    writer.writeheader()
    for row in csv.DictReader(src):
        writer.writerow({"dedup_key": row["dedup_key"], "category_slug": row["level2"],
                         "is_subscription": row["is_subscription"], "merchant": row["merchant"]})
EOF
cd apps/api && uv run finance labels import ../../data/labels/golden-spike.csv
```

Expected: `imported=412 missing=0`.

- [ ] **Step 7: First production benchmark and a label backup**

```bash
cd apps/api
uv run finance eval-categorization --note "first production run: pairing, system rules, jev"
uv run finance labels export
```

Expected: the report prints; level-2 precision at 0.95 is in the same range as the spike (about 97–99 %) or better, because pairing and rules now resolve 38 rows deterministically; a new last line in `docs/evals/HISTORY.md`. If the numbers are clearly worse than the spike's (more than about ten rows), stop and investigate before continuing (compare `eval-output/<run>/rows.csv` with the spike's `review_v7.csv`).

- [ ] **Step 8: Documentation**

- `README.md`: in "How jev categorizes transactions", add the cascade order (pairing → system rules → jev → merchant defaults → review) in one sentence, and a short "Measuring it" paragraph linking `docs/evals/HISTORY.md` and naming `uv run finance eval-categorization`. In "Local setup", add `uv run finance seed` after `supabase db reset`, and `uv run finance categorize` / `uv run finance labels export` to the commands list.
- `CLAUDE.md` Commands block: add `cd apps/api && uv run finance seed`, `uv run finance categorize [--all]`, `uv run finance eval-categorization --note "..."`, `uv run finance labels export|import`, and the rule "never `supabase db reset` without `finance labels export` first".
- Spike `README.md`: one line under "How to rerun": the spike scripts are history; measure changes with `finance eval-categorization`.

- [ ] **Step 9: Final verification and commit**

Run: `cd apps/api && uv run task test && uv run task test-integration && uv run task lint` and `cd apps/web && npm run lint && npx tsc --noEmit && npm run build`
Expected: all PASS.

```bash
git add README.md CLAUDE.md docs/evals/HISTORY.md docs/superpowers/spikes/2026-09-23-jev-categorization/README.md
git commit -m "docs: document the categorization commands and record the first benchmark"
```
