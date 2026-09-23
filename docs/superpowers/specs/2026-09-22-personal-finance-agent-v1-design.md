# personal-finance-agent — v1 design

Date: 2026-09-22
Status: approved by Raul on 2026-09-22 (see section 16)
Owner: Raul Vazquez

## 1. Purpose

A local-first personal finance assistant that Raul uses daily and that anyone
can self-host by adding their own API keys and bank exports. v1 answers four
needs:

1. Import bank exports from several accounts into one normalized ledger
   without ever duplicating a transaction.
2. Categorize every transaction with a cascade: deterministic rules first,
   jev (TypeSafe AI System One model) for the unknown, a human review inbox
   for the uncertain.
3. Show simple dashboards (spend by category, monthly trend, savings,
   subscriptions) that refresh on every import.
4. Chat with the ledger ("how much have I spent at Mercadona this week?")
   through an LLM agent that queries a semantic layer, never raw files.

Non-goals for v1 are listed in section 12.

## 2. Guiding principles

- KISS and speed of development. The least durable code that solves the real
  problem. Best practices where they are cheap: typed boundaries, tests for
  deterministic logic, CI, tracing.
- Code owns control flow. jev supplies narrow semantic judgement where rules
  fail; the LLM generates text and SQL. Anything that can be deterministic is
  deterministic (dedup, transfer pairing, SQL safety, aggregations).
- Everything user-specific lives in configuration or the database, never in
  code: accounts, categories, rules, semantic descriptions, thresholds. A
  future onboarding wizard only has to write to those places.
- Everything in English: code, comments, README, commits, UI copy.
- Simplicity is a hard requirement, not taste. Prefer 15 readable lines over
  30 clever ones. Use each library the way its documentation recommends
  instead of wrapping it. Small files with one responsibility, plain
  functions over classes unless state is real, no abstractions for a single
  caller. A reviewer should understand any module in one read.
- Privacy: bank data stays on the user's machine or their own Supabase
  project. Only transaction descriptions and aggregates are sent to jev, the
  LLM and Langfuse.

## 3. Architecture

Monorepo with two applications and one database.

```
personal-finance-agent/
├── apps/
│   ├── api/          Python 3.12, FastAPI, LangChain/LangGraph, typesafe-sdk
│   └── web/          Next.js (App Router), TypeScript, Tailwind, shadcn/ui, Recharts
├── supabase/         SQL migrations, seed data (categories, semantic layer)
├── docs/
├── docker-compose.yml
└── .github/workflows/
```

Data flow:

```
bank export ──▶ POST /imports ──▶ adapter ──▶ normalize ──▶ dedup upsert ──▶ transactions
                                                            │
                                            categorization cascade (rules → jev → review)
                                                            │
web dashboards ◀── GET /dashboard/* ◀── SQL views ◀─────────┘
web chat ◀── SSE ◀── POST /chat ──▶ jev router ──▶ LangChain agent ──▶ run_sql (read-only)
```

The web app talks only to the API in v1. The API holds the database
credentials. This keeps one typed contract (OpenAPI → generated TypeScript
types) and no secrets in the browser. When auth arrives (v2) dashboard reads
can move to supabase-js with row-level security.

### 3.1 Database: Supabase Postgres

Decision: Supabase (hosted Postgres) instead of DuckDB.

Why: the UI is Next.js, so a Python-only embedded database would force every
read through the API and offer no path to auth, multi-user or hosting. Postgres
on Supabase is the standard choice for this class of open-source project
(Maybe, Ghostfolio and Firefly III all run on Postgres), Raul already knows it,
and it gives auth, storage and a local Docker stack (`supabase start`) for
free. Analytical volume (a few thousand rows per year) is trivial for
Postgres.

Cost of the decision: an open-source user needs a free Supabase project or
Docker. Documented in the README as the one setup step beyond API keys.

Access from Python: `psycopg` (v3) with a small pool and plain SQL. Two roles:
`app` (read/write, used by ingestion and labelling) and `readonly` (used by
the agent's SQL tool). Migrations via the Supabase CLI in `supabase/migrations`.

### 3.2 Schema (v1)

| Table | Purpose | Key columns |
|---|---|---|
| `accounts` | one row per bank account, auto-created from the IBAN in a statement header | `id`, `bank` (`bbva`, `caixabank`), `iban` (unique), `name` (defaults to bank + last 4 digits, user-editable), `currency` |
| `imports` | one row per uploaded file | `id`, `account_id`, `filename`, `file_sha256`, `imported_at`, `rows_total`, `rows_new`, `rows_duplicate` |
| `transactions` | the normalized ledger | `id`, `account_id`, `import_id`, `booked_at`, `value_date`, `amount` (signed, numeric(12,2)), `currency`, `description_raw`, `merchant`, `balance_after`, `dedup_key` (unique), `tx_type` (`income`/`expense`/`transfer`), `category_slug`, `category_source` (`rule`/`jev`/`user`/`none`), `category_confidence`, `jev_suggestions` (jsonb top-3), `is_subscription`, `transfer_pair_id`, `needs_review` |
| `categories` | two-level taxonomy | `slug` (pk), `tx_type`, `level1`, `level2`, `description` (also used as jev criteria) |
| `rules` | deterministic categorization | `id`, `match_type` (`merchant_exact`/`contains`/`regex`), `pattern`, `category_slug`, `is_subscription`, `created_from_transaction_id` |
| `transaction_labels` | history of every label applied | `transaction_id`, `category_slug`, `source`, `confidence`, `labeled_at` (user labels become the golden set for Raul's own evals) |
| `semantic_schema` | natural-language schema | `table_name`, `column_name` (null = table row), `description`, `examples` (jsonb), `synonyms` (text[]) |
| `semantic_metrics` | named metrics | `name`, `description`, `sql_expression` |
| LangGraph checkpoint tables | chat memory per thread | managed by `langgraph-checkpoint-postgres` |

Views for dashboards and the agent: `v_monthly_summary`, `v_spend_by_category`,
`v_subscriptions`, `v_review_queue`, `v_transactions_enriched` (joins
categories and accounts; the agent queries this, not the base table).

## 4. Ingestion

### 4.1 Adapters

The sample files Raul has are PDF statements, not CSV exports, so v1 parses
PDFs with `pdfplumber`. CSV or XLSX exports are a second adapter per bank
when they become available; the protocol is format-agnostic.

One adapter per bank and format:

```python
class BankAdapter(Protocol):
    bank: str
    def sniff(self, text: str) -> bool: ...          # recognises the statement from its first page text
    def parse(self, pdf_bytes: bytes) -> ParsedStatement: ...
```

`ParsedStatement` carries a `StatementHeader` (`bank`, `iban`, `period_start`,
`period_end`) and a list of `NormalizedTransaction` (`booked_at`,
`value_date | None`, `amount` signed `Decimal`, `currency`, `description_raw`,
`merchant`, `balance_after | None`). Both are Pydantic models.

Observed layouts (from the sample statements in `data/raw/`, git-ignored):

- **CaixaBank** movements PDF: header with `Titular`, `IBAN` and `Periodo`;
  then one line per movement `CONCEPT dd/mm/yyyy ±amount€ balance€`, newest
  first, continuing across pages. Amount and balance are sometimes glued
  (`+2326,31€38.066,79€`). No `pdfplumber` tables; a line regex covers every
  row.
- **BBVA** monthly statement PDF: header `EXTRACTO DE <MONTH> <YEAR>` and
  `IBAN`; rows `dd/mm dd/mm CONCEPT ±amount balance` (operation date, value
  date, no year) followed by one detail line with a reference number and the
  merchant. Text must be extracted with `x_tolerance=1`, otherwise words are
  glued. Each page ends at a footer starting with `Todos los importes`. The
  year comes from the header; a December value date in a January statement
  belongs to the previous year.

Adapters are split in two layers so tests need no PDFs: a pure
`parse_text(text) -> ParsedStatement` function tested with short synthetic
text fixtures (fake IBANs and names), and a thin `parse(pdf_bytes)` that
extracts text with `pdfplumber` and calls it. An integration test, run
manually, checks the real files in `data/raw/`.

Account resolution: the IBAN in the header selects the account; unknown IBANs
create an account named `<bank> ····<last4>`. No manual account picker is
needed on upload.

Adding a bank means adding one adapter module and one text fixture test.

### 4.2 Merchant normalization

Deterministic cleanup of `description_raw` into `merchant`: strip bank
prefixes ("COMPRA TARJ", "PAGO EN", "RECIBO", card numbers, dates, city
suffixes), collapse whitespace, upper-case. Bank-specific prefix lists live
in each adapter. Rules match on `merchant`, so normalization quality directly
reduces jev calls.

### 4.3 Deduplication

Bank exports carry no stable transaction id, so we compute one:

```
dedup_key = sha256(iban | booked_at | amount | normalized(description_raw) | balance_after | occurrence_index)
```

The key hashes the account IBAN rather than `account_id`: the IBAN is known
before the account row exists and stays stable if the database is rebuilt.
`occurrence_index` is the position among identical tuples within the same
file (two identical coffees the same day get 0 and 1). Both sample banks print
the balance after each movement, which makes the key unambiguous in practice. Loading is
`INSERT ... ON CONFLICT (dedup_key) DO NOTHING`. Each import records
`rows_new` and `rows_duplicate`, shown in the UI. Uploading the same file, or
overlapping date ranges from the same account, is harmless by construction.

Known limitation: if a bank changes the description of a settled transaction
between two exports, it appears twice. Exports normally contain settled rows
only; documented in the README.

### 4.4 Transfers between own accounts

Deterministic pairing after each import: same absolute amount, opposite sign,
different accounts, booking dates within 2 days, neither already paired. Both
rows get `tx_type = transfer` and a shared `transfer_pair_id`, and are
excluded from income and expense totals. One-sided transfers (to accounts not
imported) are handled by rules or jev with a `transfer` category.

### 4.5 Entry points

- Web: `/imports` page, upload one or more statements, see the summary per file.
- CLI: `uv run finance import <file>...` for the daily habit. There is no
  `--account` flag: the IBAN in the statement header resolves the account
  (section 16, point 3).
- Watched folder and open-banking sync are v2 (section 12).

## 5. Categorization cascade

```
new transaction
   │
   ├─ 1. rules (merchant_exact → contains → regex)     confidence 1.0, source=rule
   │
   ├─ 2. jev batch                                     source=jev
   │       confidence ≥ threshold (default 0.85) ──▶ accept
   │       confidence <  threshold ──▶ needs_review=true, keep top-3 suggestions
   │
   └─ 3. review inbox (human)                          source=user
           label + optional "create rule for this merchant" (default on)
```

### 5.1 jev call shape

One `system_one` call per transaction, sent concurrently with a bounded
semaphore (default 8) and the SDK's retry policy. Questions are independent,
so they travel together:

```python
state = {
    "description": tx.description_raw,
    "merchant": tx.merchant,
    "amount": str(tx.amount),
    "direction": "outgoing" if tx.amount < 0 else "incoming",
    "bank": account.bank,
}
questions = {
    "category": Choice(
        instructions="Which category best describes this bank transaction",
        criteria={slug: description for slug, description in categories_for(direction)},
    ),
    "is_subscription": Noul(
        instructions="This is a recurring subscription charge, such as streaming, telecom, gym, insurance or software",
    ),
}
```

Only categories matching the transaction direction are offered, which keeps
the option list small (about 25) and avoids literal-reading traps.
Category descriptions in the `categories` table double as jev criteria, so
improving one improves the other. `tx_type` is derived in code: `transfer`
when paired or when the category is a transfer category, else by sign.

### 5.2 Confidence gate

Threshold is a setting, default 0.85 for `category`; `is_subscription` uses
`noul > 0.7`. Thresholds are per-decision because consequences differ. The
review inbox is the safety net: nothing under the threshold is silently
accepted.

### 5.3 Learning from corrections

A user label writes `transaction_labels`, updates the transaction, and (when
the checkbox is on) inserts a `merchant_exact` rule. Future transactions from
that merchant never reach jev. A "recategorize all" action re-runs the cascade
over every non-user-labelled transaction; with output tokens free and input at
$0.042 per million tokens, re-labelling years of history costs cents.

## 6. Subscriptions

A subscription is a flag, not a category: Netflix is `leisure > entertainment`
with `is_subscription = true`. Sources of the flag: jev (`is_subscription`),
rules, user. `v_subscriptions` groups flagged expenses by merchant and reports
last charge, typical amount, inferred cadence (monthly or yearly from median
gap) and monthly-equivalent cost. The `/subscriptions` page lists active ones
(charged in the last 45 days for monthly, 400 for yearly) and the total.
A deterministic recurrence detector (same merchant, amount within 10 percent,
3 or more charges at a regular gap) is a stretch goal in slice 2.

## 7. Category taxonomy (v1 seed)

Minimal, two levels, per transaction type. Slugs are English; the UI shows
`level1 > level2`.

| Type | Level 1 | Level 2 |
|---|---|---|
| expense | shopping | groceries, tobacco, home_goods, fashion, electronics, other_shopping |
| expense | home | rent_mortgage, utilities, internet_phone, home_insurance, maintenance |
| expense | leisure | restaurants_bars, entertainment, sports_gym, culture_events |
| expense | transport | fuel, public_transport, taxi_rideshare, parking_tolls, car_costs |
| expense | cash | atm_withdrawal |
| expense | health | pharmacy, medical, health_insurance |
| expense | travel | flights, lodging, travel_other |
| expense | financial | bank_fees, loan_payment, taxes |
| expense | other | uncategorized_expense |
| income | income | salary, refunds, investment_income, other_income |
| transfer | transfer | own_accounts, savings_investment, credit_card_payment |

Seeded from `supabase/seed/categories.yaml`; editable in the database.

## 8. Semantic layer and router context

Source of truth: `apps/api/semantic/schema.yaml` and `metrics.yaml`, versioned
in the repo and reviewed in pull requests. On API startup they are upserted
into `semantic_schema` and `semantic_metrics`.

Two consumers:

- Router and agent system prompt receive a compact catalog: one line per
  table or view, its purpose, and key columns. With fewer than ten relations
  this fits in a few hundred tokens, so it is pre-loaded into the LangGraph
  `config["configurable"]["semantic_catalog"]`, so graph nodes do no I/O,
  and is cached per process with a 5 minute TTL.
- The agent's `describe_schema(table)` tool returns the full column
  descriptions, examples and synonyms on demand.

## 9. Chat agent

Stack: LangChain `create_agent` on LangGraph, `langchain-xai` `ChatXAI(model="grok-4.7")`,
Postgres checkpointer for thread memory, Langfuse callback handler on every
run, recursion limit 12.

### 9.1 jev router node

Runs before the agent loop on every user message.

```python
state = {
    "message": last_user_message,
    "recent_turns": last_4_turns,        # compacted, no tool output
    "available_data": semantic_catalog,  # one line per table
}
questions = {
    "intent": Choice(instructions="What the user wants", criteria={
        "analytics_question": "A question answerable from the transaction data",
        "advice": "A request for financial suggestions or opinions",
        "chit_chat": "Greeting, thanks or small talk",
        "out_of_scope": "Unrelated to personal finances or this data",
    }),
    "needs_clarification": Noul(
        instructions="The question cannot be answered from the available data without one missing detail such as the time period, the account or the category",
    ),
}
```

Routing (confidence-gated, thresholds in settings):

| Result | Path |
|---|---|
| `chit_chat` | short LLM reply, no tools |
| `out_of_scope` | fixed polite message, no LLM |
| `needs_clarification > 0.7` | LLM writes one clarifying question; next turn re-enters the router with history |
| `analytics_question` | agent loop with SQL tools |
| `advice` | agent loop with an advice prompt section and a "not financial advice" note |
| `intent.confidence < 0.5` | treated as `analytics_question` (the agent can still ask) |

jev decides; the LLM writes. Router intent, confidence and latency are
recorded as Langfuse scores on the trace.

### 9.2 Tools

- `run_sql(query: str)`: parsed with `sqlglot`; only a single `SELECT` over
  the allow-listed views is accepted; a `LIMIT 200` is added when missing;
  executed with the `readonly` role and a 10 second `statement_timeout`.
  Returns compact rows plus a row count. Errors return the message and a
  recovery hint ("check column names with describe_schema").
- `describe_schema(table: str | None)`: from the semantic layer.

Labelling from chat is out of v1; the review inbox is the mutation surface.

### 9.3 Streaming

`POST /chat/{thread_id}/messages` streams tokens and tool events over SSE
using LangGraph `astream(stream_mode="messages")`. The web chat renders the
answer incrementally and shows the SQL that produced it in a collapsible
block.

## 10. API surface (v1)

| Method and path | Purpose |
|---|---|
| `GET /health` | liveness |
| `GET/POST /accounts` | list, create |
| `POST /imports` | multipart PDF upload → import summary (account resolved from the IBAN) |
| `GET /imports` | history |
| `GET /transactions` | filtered list (month, account, category, needs_review) |
| `GET /review` | review queue with jev suggestions |
| `POST /transactions/{id}/label` | set category, optional rule creation |
| `POST /categorize/run` | re-run the cascade over uncategorized or all non-user rows |
| `GET /dashboard/overview?month=` | KPIs, spend by category, monthly trend, top merchants |
| `GET /dashboard/subscriptions` | subscriptions view |
| `POST /chat/{thread_id}/messages` | SSE chat |

Pydantic models at every boundary; OpenAPI drives `openapi-typescript` for the
web client.

## 11. Web application

Next.js App Router, TypeScript, Tailwind, shadcn/ui components, Recharts
through shadcn charts. Server components fetch from the API. In v1 the browser posts uploads
straight to the API (no secrets in the browser, no auth yet, CORS limited to
the configured web origin); mutations move behind route handlers or server
actions when auth arrives in v2. Pages:

| Route | Content |
|---|---|
| `/` | month selector; KPI tiles (income, expenses, savings, savings rate); spend by level-1 donut; 12-month income vs expenses bars; top merchants; pending-review count |
| `/subscriptions` | active subscriptions table and monthly total |
| `/review` | inbox table: description, merchant, amount, jev top-3 as a select, "create rule" toggle, accept and bulk accept |
| `/chat` | streaming chat with thread list and SQL disclosure |
| `/imports` | upload, import history with new vs duplicate counts per file |
| `/settings` | accounts and thresholds (minimal in v1) |

Frontend testing in v1: type-check, lint, build in CI. Playwright smoke tests
are v2.

## 12. Out of scope for v1

Receipts (vision extraction), recommendations engine, onboarding wizard,
authentication and multi-user, open-banking sync, watched folder, deployment
target (Docker images and CI are in; hosting decision is v2, Railway or Fly
for the API, Vercel possible for the web app), jev-vs-LLM evaluation panel
(Raul runs his own evals; `transaction_labels` preserves the data for it),
labelling from chat, recording failed imports in the import history (useful
once an unattended path such as the watched folder exists).

## 13. Observability, testing, CI

- Langfuse from the first agent call: one trace per chat message and one per
  import (jev spans with input tokens, latency, confidence scores).
- Unit tests (pytest) for adapters, normalization, dedup key, transfer
  pairing, rules engine, SQL guard, confidence gate; jev and LLM mocked.
  Integration tests marked `integration` and run manually with real keys.
- GitHub Actions: `api` job (uv sync, ruff check and format, pytest unit),
  `web` job (npm ci, lint, type-check, build). Dockerfiles for both apps and a
  `docker-compose.yml` for local runs against a Supabase project.
- Settings via `pydantic-settings` reading the repo-root `.env`;
  `.env.example` lists `SUPABASE_DB_URL`, `SUPABASE_DB_URL_READONLY`,
  `TYPESAFE_API_KEY`, `XAI_API_KEY`, `LANGFUSE_PUBLIC_KEY`,
  `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` (Langfuse Python SDK v4 names;
  LangChain handler is `from langfuse.langchain import CallbackHandler`).

## 14. Delivery slices

Each slice ends usable and merged to `main`.

1. Foundation and ingestion: monorepo scaffold, Supabase migrations, accounts,
   BBVA and CaixaBank adapters, dedup, `/imports` page, transactions list.
2. Categorization: taxonomy seed, rules engine, jev batch with confidence
   gate, transfer pairing, subscription flag, `/review` inbox, recategorize.
3. Dashboards: views, `/` overview and `/subscriptions`.
4. Chat: semantic layer, jev router, agent with SQL tools, SSE, `/chat`,
   Langfuse.
5. Open-source polish: README, `.env.example`, docker-compose, CI, anonymized
   sample dataset, contribution notes for new bank adapters.

## 15. Risks and mitigations

| Risk | Mitigation |
|---|---|
| jev misreads cryptic Spanish bank descriptions | merchant normalization, rules first, review inbox, direction-filtered options, descriptions written as jev criteria |
| jev reads instructions literally | criteria name concrete situations, not adjectives; unit tests on wording changes via Raul's label history |
| LLM writes wrong SQL | semantic layer with examples, `describe_schema` tool, allow-listed views, read-only role, SQL shown to the user |
| Raul has no JavaScript background | frontend kept thin and component-based; Claude Code drafts, Raul reviews; type generation from OpenAPI reduces hand-written glue |
| Supabase adds setup friction for open-source users | documented free-tier path and `supabase start` Docker path |
| Duplicate rows from description changes | documented; manual merge is a v2 feature if it appears in practice |

## 16. Review outcome (2026-09-22)

Raul approved the spec. The three open questions closed as follows:

1. Supabase over DuckDB: confirmed.
2. v1 taxonomy: confirmed as the starting point; refine from real data.
3. Account selection on upload: not needed. Both sample banks print the IBAN
   in the statement header, so adapters resolve the account automatically
   (section 4.1).

Also added on approval: the input format for v1 is PDF statements (section
4.1) and the simplicity principle in section 2.

### Slice 1 amendments (2026-09-23)

- Section 4.3: the dedup key hashes the account IBAN instead of `account_id`.
- Section 4.5: the CLI takes one or more files and no `--account` flag.
- Section 11: in v1 the browser posts uploads straight to the API.
- Section 12: recording failed imports in the import history is out of scope.
