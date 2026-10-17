# Public face — README, architecture page and screenshots

Date: 2026-10-17
Status: draft for Raul's review
Owner: Raul Vazquez

Delivery 1 of 2. Delivery 2, the OpenWiki agent wiki, has its own spec
(`2026-10-17-openwiki-design.md`) and starts after this one merges. This spec replaces the
2026-10-16 draft (`2026-10-16-public-docs-design.md`), which was never approved.

## 1. Purpose

A stranger opens the GitHub repo and within a minute sees tally ai working and understands
what it does. The README handles that: product, three real screens and a short "how it is
built". A reviewer who wants more depth follows one link to `docs/architecture.md` and checks
each technical claim against the code, `docs/evals/HISTORY.md` and the specs.

The audience is people. Agents get the wiki in delivery 2. `CLAUDE.md` is not touched.

## 2. Decisions

| Topic | Call |
|---|---|
| Name | tally ai (the web app's title). The repo stays `personal-finance-agent` |
| Shape | A short `README.md` and a new `docs/architecture.md`. Specs, plans, money rules and the eval history are linked, never copied |
| Screens | Three, from the real UI: overview `/`, `/spending/shopping`, and one chat answer. Light theme, 1440 px wide; the height grows until the captured content is complete (overview 975, shopping 1400, chat 1940) |
| Data | Twelve synthetic months (October 2025 to September 2026). See section 5 |
| Chat capture | One real turn of the production agent (xAI grok) on the synthetic database, with Langfuse off. Fallback: a stored thread (section 6.3) |
| Machinery | A temporary generator and loader, plus their test. Deleted in the last task. The PR is squash-merged, so `main` never contains them |
| Verification | No permanent test that checks README text. Checks run once, in the plan (section 8) |
| Settings and imports | Not captured and not described as final UI. The README says only that a PDF statement is uploaded |
| Language | English, including alt text |

## 3. What the pages may claim

Every figure and mechanism below was checked against the code on 2026-10-17
(`main` at `09c7e13`). The plan re-checks them after Raul's parallel PR merges.

- **Ingestion.** BBVA and CaixaBank PDF statements. Rows are deduplicated by a key built from
  the account, date, amount, description, printed balance and occurrence. Uploading the same
  file twice adds nothing.
- **Categorization cascade.** Own-account transfers are paired, then system rules run, then jev,
  then merchant defaults, then review. jev answers one call per transaction with three typed
  questions: the merchant fragment (`Choice`), the level-2 category (`Choice`) and whether it is a
  subscription (`Noul`). Python resolves the merchant: exact match, merge at ≥ 0.8, merchant
  default. Rows under 0.95 go to `/review`, once per merchant. `link_loans` runs after save. The
  card number is stripped before jev sees the text.
- **Eval figures.** These come from the last line of `HISTORY.md` (2026-09-27, 684 golden rows).
  Level-2 accuracy is 87.0%. At the 0.95 threshold, 397 rows are accepted with 98.2% precision
  and 287 rows go to review. The spike's 99% is a different figure: 254 rows that jev scored at
  ≥ 0.95, which is why the threshold sits at 0.95. The golden set changed between lines, so the
  lines are not a trend, and run-to-run noise is about ten rows. The README never shows 99% on
  its own.
- **Money.** Every total comes from `v_transactions_enriched`. The category decides whether a row
  is income, spending or a transfer. Transfers and borrowed money are neither income nor
  spending. The contract is `docs/money-rules.md`.
- **Chat.** A ReAct agent: `langchain.agents.create_agent` with one tool, `run_sql`, and a
  LangGraph `AsyncPostgresSaver` checkpointer. It is not jev. The agent reads only the `agent`
  schema (`agent.transactions`, `agent.subscriptions`), as `agent_reader` in a read-only
  transaction. A sqlglot guard checks every query first. The YAML semantic layer is checked
  against the views at startup. The AI SDK's `useChat` is only the browser transport. Langfuse
  records one trace per turn. The v1 spec's section 9 describes a jev router in front of the
  chat. That router was not built: slice 4 spec section 16 is the amendment.
- **Limits.** The agent is told to answer with a figure it queried in the same turn, but nothing
  checks that it did (backlog item 8). There are no chat evals (item 6) and no account balances
  (item 5). Only BBVA and CaixaBank PDFs are read. The `public` tables have no row-level
  security, so this is a single-user local app, not a hosted one.
- **Privacy.** The database is local. jev receives the cleaned description. The chat model
  receives the question, the SQL and the rows it returned. Neither receives an account's IBAN or
  the raw bank description (`description_raw`).

## 4. Pages

### 4.1 `README.md` (replaced)

In this order:

1. `# tally ai` followed by one sentence: local-first personal finance; import bank PDFs, let a
   cascade categorize them, see the month, ask questions in plain language.
2. The overview screenshot, full width.
3. **What it does**: four bullets. Import without duplicates. Correct a merchant once. See
   income, spending, savings and subscriptions. Ask and see the SQL behind the answer.
4. The category page and chat screenshots, each with a one-line caption.
5. **How it is built**: a small Mermaid diagram (PDF → pairing and rules → jev → Python →
   review; one view → dashboards and chat), then four bullets. Each bullet ends with a link
   into `docs/architecture.md`:
   - jev categorizes and Python decides (`#categorization`)
   - measured, with the 2026-09-27 figures and the spike sentence (`#evals`)
   - a ReAct chat agent with read-only SQL (`#chat`)
   - one money contract for every total (`#money`)
6. **Run it locally**: requirements, `.env` with the keys that matter (`SUPABASE_DB_URL`
   required; `TYPESAFE_API_KEY` categorizes; `XAI_API_KEY` enables the chat), `supabase start`,
   migrations, `finance seed`, the API, the web. The warning that `supabase db reset` wipes
   labels (export first). The full command list lives in `CLAUDE.md`, not here.
7. **Limits**: three bullets taken from section 3.
8. License.

The README has no slice status, no list of every command, and no copy of the money rules.
Screenshots carry a caption stating that the data is synthetic.

### 4.2 `docs/architecture.md` (new)

Anchors that the README links to must keep these exact headings.

1. One opening paragraph. This page is for someone checking the code. It is not the spec,
   the prompt or the API reference. Every section links to its source.
2. `## Pipeline`: Mermaid of the real order, including `link_loans`.
3. `## Categorization`: why jev chooses among fragments rather than generating a name; the
   three questions; merchant defaults; the 0.95 threshold and where it came from. Links go to
   the jev docs pages the README already cites and to the spike write-up.
4. `## Evals`: how `finance eval-categorization` runs (dry run of the production cascade
   against the golden set, one Langfuse trace). The 2026-09-27 figures and the caveats from
   section 3. A link to `HISTORY.md`.
5. `## Chat`: the facts from section 3, plus the chat tables (`chat_threads`, `chat_messages`)
   and the limits, with links to backlog items 5, 6 and 8 and to slice 4 spec section 16.
6. `## Money`: three sentences and a link to `docs/money-rules.md`. The refund, card and Bizum
   rules are not repeated.
7. `## Privacy`: the facts from section 3.
8. `## Where to read next`: a table with README, money rules, `HISTORY.md`, the jev spike, the
   slice 4 spec, the v1 spec (amended: do not read its section 9 as the shipped chat) and the
   backlog. Plans are left out. Delivery 2 adds the agent wiki row.

## 5. Synthetic data

No figure, merchant, IBAN or statement from `data/raw/` or the real database ever enters the
generator, the screenshots or the docs.

**Accounts.** Two accounts: `Everyday` (bbva) and `Savings` (caixabank), with fake IBANs in
the test style (`ES00…`). No IBAN is shown on the three pages.

**Months.** October 2025 to September 2026, every month filled, so the "last 12 months" bars
have no gap. The default period is September 2026, which the overview compares with
August 2026.

**Income per month** (to the cent). Salary from `Northwind Labs` is 7,540.31 in ten months,
7,498.12 in March and 7,588.74 in July. `Harbor Savings` pays quarterly interest of 18–23 €.
That makes these totals:

| Month | Income | Expenses |
|---|---:|---:|
| 2025-10 | 7,540.31 | 3,842.17 |
| 2025-11 | 7,540.31 | 3,968.40 |
| 2025-12 | 7,558.73 | 4,271.86 |
| 2026-01 | 7,540.31 | 3,734.52 |
| 2026-02 | 7,540.31 | 3,811.09 |
| 2026-03 | 7,519.19 | 3,926.63 |
| 2026-04 | 7,540.31 | 4,048.27 |
| 2026-05 | 7,540.31 | 3,889.75 |
| 2026-06 | 7,560.16 | 4,112.38 |
| 2026-07 | 7,588.74 | 4,196.04 |
| 2026-08 | 7,540.31 | 4,287.91 |
| 2026-09 | 7,562.61 | 3,957.66 |

**Expenses.** About 45 rows a month, all invented merchants:

- Fixed monthly charges: rent, health insurance, car leasing, childcare, a metro pass and a
  donation.
- Four monthly subscriptions: internet, gym, streaming and an AI tool. The subscriptions card
  has real content, but subscriptions are not one of the three screens.
- Seeded variable spending: restaurants, fuel, utilities, pharmacy, pets, personal care, taxi,
  beauty, a kiosk, cinema and parking.
- A few one-off purchases: electronics in November, December gifts and home goods, a summer
  trip with flights in July and lodging in August.
- Groceries take whatever remains of each month's expense target, split over twelve tickets.
  The month then lands on its target to the cent, and groceries stay between about 570 and
  1,000 €.

Each month also moves 2,500 € from Everyday to Savings as a paired `own_accounts` transfer,
which counts in neither total. A prototype of the generator produced 557 rows that match every
target in the table above.

**How rows are stored.** Every row is already categorized: `category_source = 'user'`,
`merchant_source = 'user'`, `needs_review = false`, and `tx_type` taken from the category. That
way `finance categorize` and the review badge ignore them. Merchants are `confirmed` and have no
merge candidate. Each account gets one import per month, with `period_start` and `period_end`
set.

**Where it runs.** A database named `scratch_docs` on the local Supabase cluster. It is created
empty, then every migration is applied in order with `psql`, then `finance seed` runs with
`SUPABASE_DB_URL` pointed at it. The loader refuses to run on any database with another name.
`supabase db reset` is never used, the real database is never copied, and the repo `.env` is
never edited. Every command exports `SUPABASE_DB_URL` explicitly, because `.env` points at the
real database.

## 6. Screenshots

Captured with `agent-browser` (load `agent-browser skills get core` first) in session
`public-face`, light theme, 1440 px wide, each page as tall as its captured content
(overview 975, shopping 1400, chat 1940). The API runs on :8001 against `scratch_docs`. The web
runs as a production build on :3001 with `NEXT_PUBLIC_API_URL=http://localhost:8001`. Paths are
absolute. The console has no errors before `close`.

| File | Page | Alt text |
|---|---|---|
| `docs/images/overview.png` | `/` | tally ai overview for September 2026 with synthetic data: income, expenses, savings and the last 12 months |
| `docs/images/spending-shopping.png` | `/spending/shopping` | Shopping in September 2026: monthly bars for the last 12 months, the category treemap and top merchants |
| `docs/images/chat.png` | `/chat/<id>` | A chat answer with the SQL queries behind it opened |

### 6.1 Overview and category page

The snapshot is read back before each capture. The overview must show September 2026
income of 7,562.61 and expenses of 3,957.66 (in the UI's format), and twelve filled bars. The
shopping page must show groceries as the largest category.

### 6.2 Chat (decision: real turn)

The real API runs on :8001 against `scratch_docs`, with `XAI_API_KEY` from the environment and
`LANGFUSE_TRACING_ENABLED=false`. The question, typed into `/chat`:

> How much did I spend on restaurants each month this year, and which month was highest?

The capture is kept only if:

- every amount in the answer appears in the rows of a query from that turn (backlog 8 is the
  reason for this check), and
- those rows match a direct `psql` query on `scratch_docs`.

Otherwise the turn is asked again, at most three times, and then the plan falls back to 6.3.
The query disclosure is opened before the capture. The cost is a few cents of xAI usage.
This is a deliberate exception to the "chat checks use scripted models" rule in `CLAUDE.md`:
it is a capture, not a check.

### 6.3 Fallback: stored thread

The loader inserts one `chat_threads` row and two `chat_messages` rows. The stored query runs
as `agent_reader` against `scratch_docs`, and its real result is saved in the `QueryResult`
shape. The answer text is written by hand from that result. The page is served by
`tests/scripted_chat_server.py`, so no key is needed. If this path is used, the chat caption
says the answer was replayed from stored data.

## 7. Files

| Path | Change | Stays after the PR |
|---|---|---|
| `README.md` | replaced | yes |
| `docs/architecture.md` | new | yes |
| `docs/images/*.png` | three new captures | yes |
| `apps/api/finance/demo_ledger.py` | new generator and loader | deleted in the last task |
| `apps/api/tests/test_demo_ledger.py` | its unit test (no database) | deleted in the last task |
| `docs/superpowers/specs/2026-10-16-public-docs-design.md`, `docs/superpowers/plans/2026-10-16-public-docs.md` | untracked drafts in Raul's checkout | Raul deletes them; they are not committed |

`tests/scripted_chat_server.py` is not modified.

## 8. Verification

- **Generator.** `test_demo_ledger.py` asserts the exact income and expense totals in section 5,
  all twelve months present, groceries inside their range, invented merchants only, and fake
  IBANs only. TDD: the test is written first.
- **Facts.** A reviewer subagent traces every figure and mechanism on the two pages to
  `HISTORY.md` or to a `file:line` in the code. Any claim it cannot trace is removed or fixed.
- **Links.** A one-off command, not committed, resolves every relative link, image and anchor
  in the two pages.
- **UI.** agent-browser reads back the values in 6.1 and 6.2 before each capture.
- **Privacy.**
  - Each PNG is opened and read.
  - `git grep -E 'ES[0-9]{22}'` on the changed files finds only `ES00…` fakes.
  - A local query against the real database counts how many synthetic merchant names match a
    real merchant. It prints only the count, which must be 0.
- **Cleanup.** The loader and its test are absent, `git grep demo_ledger` finds nothing, and
  `scratch_docs` is dropped. `uv run task test` and `uv run task lint` pass, and
  `npm run lint` and the build are untouched.
- **Review.** SDD's per-task reviews, then a final whole-branch review before the PR.

## 9. Out of scope

- OpenWiki, `AGENTS.md`, any change to `CLAUDE.md` (delivery 2)
- Captures of `/settings`, `/imports`, `/review`, `/subscriptions`, phone or dark mode
- A permanent demo mode or `finance demo` command
- A live jev call, Langfuse traces, or GitHub Pages
- Rewriting specs, plans, money rules or the eval history

## 10. Success

- A fresh clone's README shows tally ai with three real screens of synthetic data, the honest
  eval figures, and links that resolve.
- `docs/architecture.md` matches section 3 and describes no jev router.
- No generator remains in the tree.
- No screenshot or doc carries a real figure, merchant or IBAN.
