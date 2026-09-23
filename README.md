# personal-finance-agent

Local-first personal finance assistant: import bank exports, categorize
transactions with a rules → jev → human cascade, explore dashboards, and chat
with your finances through an LLM agent over a semantic layer.

## Status

Slice 1 (ingestion) is complete. Design: `docs/superpowers/specs/`. Plans: `docs/superpowers/plans/`.

## Local setup

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node 22, [Supabase CLI](https://supabase.com/docs/guides/cli).

```bash
cp .env.example .env            # only SUPABASE_DB_URL is required for slice 1; the other keys are for later features
supabase start                  # local Postgres; copy the DB URL into .env as SUPABASE_DB_URL
supabase db reset               # apply migrations
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
