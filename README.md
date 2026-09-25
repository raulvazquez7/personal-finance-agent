# personal-finance-agent

Local-first personal finance assistant: import bank exports, categorize
transactions with a rules → jev → human cascade, explore dashboards, and chat
with your finances through an LLM agent over a semantic layer.

## Status

Slice 1 (ingestion) and slice 2 (categorization with jev and the `/review`
inbox) are complete. Dashboards and the chat agent come next. Design:
`docs/superpowers/specs/`. Plans: `docs/superpowers/plans/`.

## How jev categorizes transactions

Bank lines are cryptic (`PAGO CON TARJETA EN SUPERMERCADOS | 1234… SUPER ACME
0042 L`), and a person wants to see "Super Acme, Shopping > Groceries". This project
uses [jev](https://typesafe.ai), TypeSafe AI's System One model, for
the judgement calls. Deterministic Python handles everything else.

jev does not generate text. It answers typed questions about a JSON state:
a [`Choice`](https://docs.typesafe.ai/primitives/choice) returns a probability
for every option, and a [`Noul`](https://docs.typesafe.ai/primitives/noul)
returns the probability of yes. Each transaction becomes one call with three
independent questions. Operations without a merchant (ATM, card
settlement, Bizum, own transfers) are resolved by deterministic rules before
jev, and a merchant the user has already labelled keeps that label. The
cascade always runs in the same order: own-account pairing → system rules →
jev → merchant defaults → review.

```mermaid
flowchart LR
    A[PDF line] --> B["Python<br/>bank_concept, clean text,<br/>fragments, no card number"]
    B --> R{system rule?}
    R -->|ATM, Bizum, card settlement| H
    R -->|no| C{"jev System One<br/>one call"}
    C -->|Choice| D[merchant = which fragment]
    C -->|Choice| E[category = level-2 slug]
    C -->|Noul| F[is it a subscription?]
    D --> G["Python<br/>exact match on known merchants,<br/>merchant default wins,<br/>level 1 from level 2, thresholds"]
    E --> G
    F --> G
    G -->|confident| H[(labelled transaction)]
    G -->|unsure| I["/review inbox"]
    I -->|one click| J[merchant default + merge]
```

How the design follows jev's documented patterns:

- **Code proposes, jev chooses.** Python cuts the text into 1–4 word
  fragments and jev picks the brand name
  ([pre-parsed value extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook)).
  There is no merchant list to maintain: a shop in a new country works on day
  one.
- **One call, many questions.** Merchant, category and subscription are asked
  together and answered independently
  ([parallel questions](https://docs.typesafe.ai/cookbooks/parallel_questions)).
- **Two-level taxonomy from one question.** jev picks the level-2 category;
  level 1 and its confidence come from summing the leaf probabilities, so an
  uncertain "groceries vs. other shopping" still reports "Shopping" with
  confidence
  ([classification using confidence](https://docs.typesafe.ai/cookbooks/classification_using_confidence)).
- **Confidence drives routing.** Per-decision thresholds send only uncertain
  rows to a human, and the same merchant is merged only at ≥ 0.8
  ([confidence](https://docs.typesafe.ai/confidence)).

The spike on 412 real transactions (six rounds, `jev-1.13.0`) cost under
$0.05 per run with the final taxonomy of 55 categories, about 2,700 input
tokens per transaction. It unified every branch and truncation of the same
supermarket under one merchant. Against 412 hand-checked labels, jev was
right on 99% of the rows it scored at 0.95 or more, which set the acceptance
threshold; the rest goes to review, once per merchant. Round-by-round results and lessons are in
[the spike write-up](docs/superpowers/spikes/2026-09-23-jev-categorization/README.md).
Full design: spec sections 4.2 and 5.

How the numbers add up (refunds, loans, credit cards, transfers): [docs/money-rules.md](docs/money-rules.md).

### Measuring it

`cd apps/api && uv run finance eval-categorization --note "what changed"` runs
the production cascade as a dry run against your own labels (the golden set)
and appends one line to [`docs/evals/HISTORY.md`](docs/evals/HISTORY.md); the
row-level results stay in the git-ignored `eval-output/`, and the run's jev
calls form one Langfuse trace tagged `eval`. The first production run, with
pairing and system rules in front of jev, accepted 265 of 412 labelled
transactions at 0.95 with 3 errors (98.9% precision) and sent 147 to review,
against 97.2–97.6% and 158–164 for the jev-only spike runs, for about $0.04.

## Local setup

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node 22, [Supabase CLI](https://supabase.com/docs/guides/cli).

```bash
cp .env.example .env            # SUPABASE_DB_URL is required; TYPESAFE_API_KEY enables categorization, LANGFUSE_* tracing
supabase start                  # local Postgres; copy the DB URL into .env as SUPABASE_DB_URL
supabase db reset               # apply migrations (export your labels first once you have some)
(cd apps/api && uv run finance seed)   # load the category taxonomy and system rules
```

```bash
# terminal 1, from the repo root
cd apps/api && uv sync --group dev && uv run task api
```

```bash
# terminal 2, from the repo root
cd apps/web && npm install && npm run dev
```

Open http://localhost:3000/imports and upload a BBVA or CaixaBank PDF statement,
or run `cd apps/api && uv run finance import ../../data/raw/<statement.pdf>`.
With `TYPESAFE_API_KEY` set, every import is categorized right away; open
http://localhost:3000/review for what jev was unsure about.

```bash
cd apps/api
uv run finance categorize         # categorize pending rows (--all re-runs every row you have not labelled)
uv run finance labels export      # back up your labels to data/labels/ (git-ignored; --force overwrites)
uv run finance labels import ../../data/labels/<file>.csv   # restore them after a reset
```

A reset also loses the merchant defaults: the labels CSV holds labels only. To
restore, run `finance seed`, re-import the statements with `TYPESAFE_API_KEY=`
(empty, so no paid categorize run happens), `finance labels import`, then
`finance categorize`.

Real statements go in `data/raw/` (git-ignored). Uploading the same file twice
never duplicates a transaction.

## Known limitations

- If a bank changes a settled transaction's description between two exports,
  that transaction appears twice.
- Two movements are treated as the same transaction only when their date,
  amount, description and printed balance all match. With a running balance
  that requires the movements between them to net to zero (for example a
  charge, its reversal, and the same charge again on one day). If two exports
  cut in the middle of such a day each contain a different one of the matching
  movements, the later import skips it.
- A failed import (unsupported file, unreadable PDF, broken balance chain) is
  reported to you but not recorded in the import history. Nothing from the
  file is saved.
- Every upload is recorded in the import history, including re-uploads that
  add no new rows.

## License

MIT, see [LICENSE](LICENSE).
