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
| `transactions` | the normalized ledger | `id`, `account_id`, `import_id`, `booked_at`, `value_date`, `amount` (signed, numeric(12,2)), `currency`, `description_raw`, `bank_concept`, `merchant` (cleaned text), `card_last4`, `balance_after`, `dedup_key` (unique), `tx_type` (`income`/`expense`/`transfer`), `merchant_id`, `merchant_source` (`jev`/`user`/`none`), `category_source` (`rule`/`merchant`/`jev`/`user`/`none`), `merchant_confidence`, `category_slug`, `category_confidence`, `category_probabilities` (jsonb, full distribution), `is_subscription`, `subscription_score`, `transfer_pair_id`, `needs_review` |
| `merchants` | canonical merchant names, grown automatically from jev picks and user merges | `id`, `name` (unique), `match_key` (unique: upper-case letters and digits only), `confirmed` (the user checked it: no more merge suggestions), `category_slug` and `is_subscription` (nullable: the user's default for every transaction of this merchant), `merge_candidate_id` and `merge_confidence` (a pending merge suggestion) |
| `categories` | two-level taxonomy | `slug` (pk, the level-2 name), `tx_type`, `level1`, `what` and `not_for` (the jev criteria) |
| `rules` | operations without a merchant, resolved before jev | `id`, `name`, `bank` (null = any), `match_field` (`bank_concept`/`merchant`), `pattern` (case-insensitive regex), `direction` (`outgoing`/`incoming`/`any`), `category_slug`, `enabled` |
| `transaction_labels` | history of every label applied | `transaction_id`, `merchant_id`, `category_slug`, `is_subscription`, `source`, `confidence`, `model` (concrete jev version, e.g. `jev-1.13.0`), `labeled_at` (user labels become the golden set for Raul's own evals) |
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

Python only structures, it does not guess the merchant name:

- `bank_concept`: the bank's own operation label when the format has one
  (BBVA prints it before ` | `, e.g. `PAGO CON TARJETA EN SUPERMERCADOS`).
  It is the strongest category signal jev gets. Null for CaixaBank.
- `merchant`: the detail text, upper-case, whitespace collapsed, leading
  references dropped, card number removed. System rules match on it or
  on `bank_concept`.
- `card_last4`: last four digits of the card when the line has one. The full
  card number is never stored outside `description_raw` and never sent to jev.

The canonical merchant name ("Mercadona" across every branch, city and
truncation) is chosen by jev from fragments of `merchant` (section 5.1), so no
per-bank city list or merchant list is maintained by hand.

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

The ledger is one household: every imported account belongs to it, whoever
holds it. Money moving between two imported accounts, by bank transfer or by
Bizum, is internal and is excluded from income and expense totals. Counting it
would double count: a Bizum to a partner who then pays the supermarket would
show up as both a payment to a person and groceries.

Deterministic pairing after each import, before categorization: same absolute
amount, opposite sign, different accounts, booking dates within 2 days,
neither already paired, and both sides transfer operations (a case-insensitive
regex on `description_raw`, default `TRASPASO|TRANSFER|BIZUM|TRF`, kept as a
setting so two card purchases of the same amount never pair). Both rows get
`tx_type = transfer`, category `own_accounts` with `category_source = rule`,
and a shared `transfer_pair_id`; they skip jev. When the counterpart arrives in
a later import, pairing relabels the earlier row unless the user labelled it.
In the spike ledger the rule found 6 pairs, all real: 3 transfers between two
accounts of the same holder (jev had read the holder's name as another person)
and 3 Bizum payments between partners.

One-sided transfers (the other account is not imported) keep their system
rule or jev category: `TRASPASO PROPIO` stays `own_accounts`, and an unpaired
Bizum goes to `payments_to_people` or `payments_from_people`.

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
   ├─ 0. own-account pairing (section 4.4)             source=rule, no jev call
   │
   ├─ 1. system rules (operations without a merchant)   source=rule, no jev call
   │
   ├─ 2. jev: merchant name + category + subscription   (section 5.1)
   │
   ├─ 3. merchant default set by the user?             source=merchant, jev's category kept for evals
   │
   ├─ 4. confidence gate (section 5.2)                  accept, or needs_review
   │
   └─ 5. /review (human)                                source=user; the label becomes the merchant default
```

Two deterministic mechanisms, one job each:

- **System rules** handle operations whose meaning the bank fixes and whose
  text names no merchant: ATM withdrawals, credit card settlements, Bizum and
  own-account transfers. A rule is a case-insensitive regex on `bank_concept`
  or `merchant`, optionally limited to one bank and one direction; it sets the
  category, leaves the merchant empty and skips jev. The Bizum rules also stop
  the free text a person writes after `ENVIADO:` being read as a merchant.
  Rules are seeded from `supabase/seed/rules.yaml` and must not conflict (a
  test checks that no fixture is matched by two rules with different
  categories). In the
  spike data, 9 seed rules matched 32 rows with no conflict and moved 9 of
  them out of review. Adding a bank or an operation means adding a row; rules
  are not a place for merchants.
- **Merchant defaults** make "review a merchant once" true. jev still names
  the merchant (every branch and truncation resolves to one `merchant_id`,
  section 5.1), and when that merchant has a `category_slug` or
  `is_subscription` set by the user, those win over jev. A text rule per
  merchant would need one rule per spelling (`ACME 0042` and `ACME C.C.`);
  the merchant id covers them all, and the extra jev call costs about $0.0001.

### 5.1 jev call shape

Validated by the spike in `docs/superpowers/spikes/2026-09-23-jev-categorization/`
(412 real transactions, five rounds). jev answers closed questions only
(`Choice`, `Noul`, `Score`), so code generates the options and jev chooses.

**Contracts**

| Step | Owner | In | Out |
|---|---|---|---|
| 1. Prepare | Python | transaction row | `state`, merchant fragments, category options |
| 2. First call | jev | `state` + three questions | probabilities per question |
| 3. Resolve merchant | Python | chosen fragment | existing merchant (exact key), shortlist, or new |
| 4. Same-merchant call | jev, only with a shortlist | `state` + `candidate_name` + shortlist | probabilities |
| 5. Apply | Python | all probabilities | labels, confidences, `needs_review` |

**Step 1.** Fragments are every run of one to four consecutive words of
`merchant`, split on spaces and `* / ,`, dropping any token that contains a
digit (reference codes, branch numbers). Category options are the level-2
slugs for the direction (expense or income) plus the transfer slugs.

**Step 2.** One call, questions evaluated independently (speculative fan-out):

```python
state = {"bank": "bbva", "bank_concept": "PAGO CON TARJETA EN SUPERMERCADOS",
         "merchant_text": "SUPER ACME 0042 L", "amount": "-23.28", "direction": "outgoing"}
questions = {
    "merchant_name": Choice(
        instructions={"question": "Which fragment of `merchant_text` is the business or brand name, as a person would say it?",
                      "not_for": "city names, country codes, branch numbers, legal suffixes like SL or SA, card numbers"},
        criteria={fragment: None for fragment in fragments} | {"none": {"what": "the text names no business: a person, a generic operation (BIZUM, TRANSFER) or a code"}},
    ),
    "category": Choice(
        instructions="Which category best describes this bank transaction",
        criteria={slug: {"group": level1, "what": description, "not_for": ...} for ...},
    ),
    "is_subscription": Noul(instructions={
        "question": "This is a recurring charge for a service the person can cancel",
        "examples": "streaming, software and AI tools, telecom, gym, insurance, memberships",
        "not_for": "electricity, gas or water bills, rent, mortgage, loan repayments, one-off purchases"}),
}
```

**Step 3.** Brand confidence is the sum of the probabilities of the fragments
nested with the chosen one (`ACME` and `ACME FOODS` are both right and split
the mass). The chosen name's `match_key` (letters and digits only) is looked
up in `merchants`; a hit is the same merchant. Otherwise the shortlist is
every merchant that shares a word (longer than two letters, not a legal
suffix) with the chosen name.

**Step 4.** Only with a non-empty shortlist (about 3 percent of rows in the
spike): `known_merchant` Choice over the shortlist names plus `none`, with
`candidate_name` in the state and `not_for: "a different business that only
shares the town, the street or the kind of shop"`. Never merge on doubt:
a wrong merge corrupts analytics silently, a duplicate is one click in
`/review`.

**Step 5.** jev picks level 2; level 1 is the parent slug in `categories`,
and its confidence is the sum of its leaves' probabilities
([classification using confidence](https://docs.typesafe.ai/cookbooks/classification_using_confidence)).
`tx_type` is derived in code: `transfer` when paired or when the category is
a transfer category, else by sign.

Calls run with a bounded semaphore (default 8) and the SDK retry policy; the
same-merchant step serializes merchant creation so two concurrent rows cannot
create the same merchant twice. Every call is wrapped in a Langfuse span with
`model`, `request_id`, `usage` and the probabilities. Category descriptions in
`categories` double as jev criteria. Cost in the spike with the final taxonomy:
about 2,700 input tokens per transaction, $0.046 for 412 rows.

### 5.2 Confidence gate

Thresholds are settings, per decision because consequences differ:

| Decision | Accept | Otherwise |
|---|---|---|
| Category (level 2) | confidence >= 0.95 | `needs_review`; level 1 is still shown when its summed confidence is >= 0.95 |
| Merchant name (new) | brand confidence >= 0.5 | merchant left empty, `needs_review` |
| Merge into a known merchant | confidence >= 0.8 | new merchant; 0.5 to 0.8 appears in `/review` as a merge suggestion |
| Subscription (expenses only) | noul > 0.7 | not flagged; never sends a row to `/review` on its own, but rows already in `/review` show a subscription toggle |

The category threshold comes from 412 labelled transactions (spike round 6).
jev is overconfident below 0.95: rows at 0.85 to 0.95 were right 76 percent
of the time, rows at 0.95 or more 99 percent. With system rules first, 0.95
accepts 232 of the 380 remaining rows with 2 errors (0.85 would accept 265
with 10) and sends 72 distinct merchants to review. Review happens once per
merchant (section 5), so the stricter threshold is a one-off cost on the
first import. `finance eval-categorization` re-checks it as labels grow.
The review inbox is the safety net: nothing under a threshold is
silently accepted.

### 5.3 Learning from corrections

A user label writes `transaction_labels` and updates the transaction.
Confirming a merchant row in `/review` (section 11.1) sets the merchant
default and relabels that merchant's rows whose `category_source` is `jev` or
`merchant`; rows labelled one by one (the expanded view, used for mixed
merchants such as marketplaces) stay as they are. Future transactions of
that merchant take the default without review. Merging two merchants in
`/review` repoints their transactions and keeps the surviving name and
default. A "recategorize all" action re-runs the cascade over every
non-user-labelled transaction; with output tokens free and input at
$0.042 per million tokens, re-labelling years of history costs cents.

## 6. Subscriptions

A subscription is a flag, not a category: Netflix is `leisure > entertainment`
with `is_subscription = true`. It means a recurring charge for a service the
person can cancel: streaming, software and AI tools, telecom, gym, insurance,
memberships. Utility bills, rent, mortgage and loans are recurring too, but
they are commitments rather than subscriptions and would only add noise to
the subscriptions page.

Sources of the flag, strongest last: jev (`is_subscription` > 0.7, expenses
only), the merchant default (set with "apply to this merchant" in `/review`,
together with the category), and the user on a single row. jev decides row by
row, which handles mixed merchants: in the spike, Amazon Prime charges scored
about 0.9 and marketplace orders about 0.2.

Measured against the golden set (spike round 7): 26 rows flagged, all right,
26 of 30 subscriptions found. The misses scored 0.35 to 0.63 (a new AI tool,
an IPTV service, two Amazon video charges); a band that sent 0.3 to 0.7 to
review would have added 13 rows to find those few, so instead `/review` shows a
subscription toggle on rows that are there for their category, and the
merchant default makes the fix permanent.

`v_subscriptions` groups flagged expenses by merchant and reports last charge,
typical amount, inferred cadence (monthly or yearly from median gap) and
monthly-equivalent cost. The `/subscriptions` page lists active ones (charged
in the last 45 days for monthly, 400 for yearly) and the total.

## 7. Category taxonomy (v1 seed)

Two levels, per transaction type, meant to fit any household rather than only
the sample data (children, pets, education and public benefits are included
even without spend yet), while staying small enough for review. Slugs are
English and stable; the UI shows `level1 > level2`. Validated in spike
rounds 5 and 6 (`docs/superpowers/spikes/2026-09-23-jev-categorization/`).

| Type | Level 1 | Level 2 |
|---|---|---|
| expense | home | rent, mortgage, utilities, internet_phone, home_insurance, maintenance |
| expense | shopping | groceries, fashion, electronics, home_goods, beauty_perfumery, hobbies, tobacco, other_shopping |
| expense | leisure | restaurants_bars, entertainment, culture_events, sports_gym, gambling_lottery |
| expense | transport | fuel, public_transport, taxi_rideshare, parking_tolls, car_costs |
| expense | travel | flights, lodging, travel_other |
| expense | technology | software_ai |
| expense | health | pharmacy, medical, health_insurance, personal_care |
| expense | education | tuition, courses, books_supplies |
| expense | family | childcare_kids, pets |
| expense | people | payments_to_people |
| expense | giving | donations |
| expense | financial | bank_fees, loan_payment, taxes, other_insurance |
| expense | cash | atm_withdrawal |
| expense | other | uncategorized_expense |
| income | income | salary, self_employment, pension_benefits, refunds, investment_income, payments_from_people, other_income |
| transfer | transfer | own_accounts, savings_investment, credit_card_payment |

Each level-2 row carries its jev criterion as `what` (what belongs here) and,
where a neighbour competes, `not_for` (what goes to the neighbour instead),
following the [contrastive criteria pattern](https://docs.typesafe.ai/concepts/how-to-build-with-system-one).
The validated texts live in the spike's `run.py` and move verbatim to
`supabase/seed/categories.yaml`, the seed of the `categories` table.

Choices worth knowing:

- A subscription is a flag, not a category (section 6).
- There is no gifts category: bank text cannot tell a gift from a purchase, so
  it goes to the shop's category.
- Bizum and transfers to or from individuals outside the ledger get their own
  buckets (`people`, `payments_from_people`) because their purpose is not in
  the text (between imported accounts they are internal, section 4.4);
  the user relabels them in `/review` when it matters.
- Rental income stays in `other_income` until someone needs it.
- Software, AI and productivity tools (`technology > software_ai`) are
  neither leisure nor goods; streaming stays in `entertainment`. Food
  delivery memberships such as Uber One belong to `restaurants_bars`.

Categories are data: adding one is inserting a row with its criterion, with no
code or prompt change. Editing the taxonomy from the UI is v2 (section 12);
v1 keeps slugs immutable so rules, labels and the golden set never break.

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
| `GET /review` | review items (section 11.1) |
| `GET /categories` | taxonomy tree for pickers |
| `GET /merchants?q=` | merchant autocomplete |
| `POST /merchants/{id}/review` | confirm a merchant: category, subscription, optional rename; sets the default and relabels its non-user rows |
| `POST /merchants/{id}/merge`, `POST /merchants/{id}/dismiss-merge` | accept or reject a merge suggestion |
| `POST /transactions/{id}/label` | label one transaction: existing or new merchant, category, subscription |
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
| `/review` | review inbox, one row per merchant (section 11.1) |
| `/chat` | streaming chat with thread list and SQL disclosure |
| `/imports` | upload, import history with new vs duplicate counts per file |
| `/settings` | accounts and thresholds (minimal in v1) |

### 11.1 Review inbox

Simple, minimal, clear; a base to extend later. One sentence of copy, a
progress bar ("12 of 72") and one row per merchant, not per transaction,
ordered by total spend so the largest merchants come first. Rows without a
merchant (payments to people, opaque codes) appear one by one.

```
 Review                                                    12 of 72 ▓▓▓░░░░░░
 Confirm or fix. Your answer applies to every transaction of the merchant.
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ ▸ ACME FROZEN YOGURT 0042           ×5   −43.13 €                        │
 │   Merchant [ Acme Frozen   ▾]   Category [ groceries  ▾] ·89   Shopping  │
 │                                              Subscription ○   [ ✓ ]      │
 ├──────────────────────────────────────────────────────────────────────────┤
 │   Same merchant as ACME FOODS?                     [ Merge ]  [ No ]     │
 └──────────────────────────────────────────────────────────────────────────┘
```

- Bank text (muted, truncated), a transaction count and the total amount.
- Merchant: searchable combobox over known merchants with "Create '…'";
  picking another merchant merges, typing a new name renames.
- Category: searchable level-2 combobox grouped by level 1, jev's top three
  first; confidence only as a small muted number beside it.
- Level 1: read-only, follows the category.
- Subscription: switch, on when jev scored > 0.7.
- Confirm: the row fades out with a "Confirmed · Undo" toast; the request is
  sent when the toast closes (or when the page is left), so undo simply
  cancels it.
- Expanding a merchant row lists its transactions for one-off labels, which
  do not touch the merchant default.
- A merge suggestion (0.5 to 0.8) is an inline line with Merge and No; No
  marks the merchant `confirmed` so it is not suggested again.
- No bulk accept: with one row per merchant the first import is about 72
  clicks, and accepting everything at once is what the 0.95 threshold exists
  to prevent.
- Responsive: a two-line grid row on desktop, stacked cards below `md`.
  shadcn/ui `Command` + `Popover` (combobox), `Switch`, `Badge`, `Progress`,
  `Button`, `Sonner` (toast). Empty state: "All caught up". The pending count
  shows in the navigation and on the dashboard.

`GET /review` returns items of kind `merchant` or `transaction`, each with its
transactions, count, total, suggestion (category, confidence, level 1,
subscription), jev's top three and any merge suggestion. Every action writes
`transaction_labels`, the source of truth for evals (section 13).

Frontend testing in v1: type-check, lint, build in CI. Playwright smoke tests
are v2.

## 12. Out of scope for v1

Receipts (vision extraction), recommendations engine, onboarding wizard,
authentication and multi-user, open-banking sync, watched folder, deployment
target (Docker images and CI are in; hosting decision is v2, Railway or Fly
for the API, Vercel possible for the web app), jev-vs-LLM evaluation panel
(Raul runs his own evals; `transaction_labels` preserves the data for it),
labelling from chat, editing the category taxonomy from the UI (v1 edits
`categories` in the database; slugs stay immutable), a recurrence detector that flags subscriptions from charge history (same
merchant, amount within 10 percent, 3 or more charges at a regular gap; the
sample data has at most two or three months per account, too little to
validate it), recording failed imports in the import history (useful
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

### 13.1 Categorization evals

A benchmark to measure every change to criteria, thresholds, rules or the jev
version against the user's own labels, with the production code.

| | |
|---|---|
| Golden set | the latest `source = user` label per transaction in `transaction_labels`: the single source of truth, growing with every label made in `/review` or the UI |
| Command | `uv run finance eval-categorization [--limit N] [--note "..."]` runs the production categorizer as a dry run (pairing, system rules, jev, thresholds) over the labelled transactions; it writes nothing to the database |
| Per run | `eval-output/<timestamp>/` (git-ignored): `rows.csv` (id, golden, predicted, confidences), `summary.json` (date, jev version, hash of taxonomy and rules, metrics) and `report.md` (readable tables) |
| History | one line appended to `docs/evals/HISTORY.md` (tracked; metrics only, no bank data) so the evolution is visible |
| Metrics | level-2 and level-1 accuracy; accuracy per confidence bucket; accepted rows, errors and review load at 0.80 / 0.85 / 0.90 / 0.95; subscription precision and recall; merchant accuracy by `match_key` |

The dry run ignores merchant defaults and builds its merchant roster within the
run: defaults come from the same user labels, so using them would score the
labels against themselves. The eval measures what the system decides without
the user. jev varies by about ten rows between identical runs (spike round 7);
the report says so. Each run costs about $0.05 per 400 labelled rows, so it
stays out of CI; its jev calls are traced in Langfuse with an `eval` tag.
Metrics are a pure function with unit tests on synthetic rows. Once the
command exists, the spike's `run.py` and `report.py` are history, not a
second implementation.

`supabase db reset` wipes `transaction_labels`, so labels travel as CSV keyed
by `dedup_key`: `finance labels export [file]` (default under the git-ignored
`data/labels/`) and `finance labels import <file>`, which also loads the
spike's 412-row golden set as the first user labels. Langfuse Datasets and
Experiments are v2.

## 14. Delivery slices

Each slice ends usable and merged to `main`.

1. Foundation and ingestion: monorepo scaffold, Supabase migrations, accounts,
   BBVA and CaixaBank adapters, dedup, `/imports` page, transactions list.
2. Categorization: taxonomy and system-rule seeds, `merchants`, own-account
   pairing, jev categorizer (merchant, category, subscription) with the
   confidence gate, merchant defaults, `/review` inbox, recategorize,
   `finance eval-categorization` and `finance labels export/import`.
3. Dashboards: views, `/` overview and `/subscriptions`.
4. Chat: semantic layer, jev router, agent with SQL tools, SSE, `/chat`,
   Langfuse.
5. Open-source polish: README, `.env.example`, docker-compose, CI, anonymized
   sample dataset, contribution notes for new bank adapters.

## 15. Risks and mitigations

| Risk | Mitigation |
|---|---|
| jev misreads cryptic Spanish bank descriptions | merchant normalization, rules first, review inbox, direction-filtered options, descriptions written as jev criteria |
| jev reads instructions literally | criteria name concrete situations, not adjectives; every wording change is measured with `finance eval-categorization` against the golden set |
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

### Slice 2 amendments (2026-09-23)

Decided with Raul after the jev spike
(`docs/superpowers/spikes/2026-09-23-jev-categorization/README.md`):

- Section 3.2: new `merchants` table; `transactions` gains `bank_concept`,
  `card_last4`, `merchant_id`, `merchant_source`, `merchant_confidence`,
  `category_probabilities` (replaces `jev_suggestions`) and
  `subscription_score`; `transaction_labels` records the jev `model`.
- Section 4.2: Python structures (`bank_concept`, cleaned `merchant`,
  `card_last4`) and never guesses the merchant name; the card number never
  reaches jev.
- Section 5.1: contracts between Python and jev; merchant chosen by jev from
  code-generated fragments, then an exact key match, then a same-merchant
  question over a shortlist; jev picks level 2, level 1 is derived.
- Section 5.2: thresholds per decision, merge only at >= 0.8.
- Two-level analytics (level 1 and level 2) is a requirement.
- Section 7: new taxonomy (14 expense groups, 55 level-2 slugs in total) with
  `what`/`not_for` criteria, validated in spike rounds 5 and 6; `rent` and
  `mortgage` are separate, `technology > software_ai` is new; UI editing of
  categories is v2 (section 12).
- Sections 3.2, 5 and 5.3: system rules (regex on `bank_concept` or
  `merchant`, per bank and direction) resolve operations without a merchant
  before jev; the user's category for a merchant is stored on `merchants` and
  wins over jev, so each merchant is reviewed once. `merchant_exact` text rules
  are dropped.
- Section 5.2: category threshold 0.95 for level 2 and level 1, chosen
  against 412 labelled transactions (the first golden set, kept outside git
  until `transaction_labels` holds it).
- Section 4.4: the ledger is one household; transfers and Bizum between any
  two imported accounts pair deterministically before categorization (guarded
  by a transfer-operation regex), become `own_accounts` and leave the totals.
- Section 6: a subscription is a cancellable recurring service (not utilities,
  rent, mortgage or loans); jev flags at > 0.7 with no review band; the flag is
  also a merchant default; the recurrence detector moves to v2 (section 12).
- Sections 10 and 11.1: `/review` has one row per merchant (merchant,
  level-2 category, derived level 1, subscription; confidence as a small
  number), expand for one-off labels, inline merge suggestions, undo toast, no
  bulk accept; endpoints for categories, merchant autocomplete, merchant
  confirm, merge and dismiss; `transaction_labels` gains `is_subscription`.
- Section 13.1: `finance eval-categorization` (dry run of the production
  categorizer against `transaction_labels`), per-run `rows.csv`,
  `summary.json` and `report.md`, a tracked `docs/evals/HISTORY.md`, and
  `finance labels export/import` so the golden set survives database resets.
- Known ambiguity left to review: a mortgage lender's direct debit can read
  as a loan; labelled once in `/review`, it becomes the merchant default.

