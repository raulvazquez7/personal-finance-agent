# personal-finance-agent — Claude Code context

Project layer on top of `~/.claude/CLAUDE.md`. Raul is the engineering lead;
follow the joint-decision loop for anything not already in the spec or plan.

## What this is

Open-source, local-first personal finance assistant. Bank PDF statements are
imported into Supabase Postgres, categorized through a cascade (rules → jev →
human review), shown in Next.js dashboards, and queryable through a LangChain
agent over a semantic layer. Design: `docs/superpowers/specs/`. Plans:
`docs/superpowers/plans/`. Read the spec before touching architecture.

## Workflow

- Superpowers: brainstorm → spec → plan → subagent-driven-development, TDD,
  verification before claiming done. One plan per delivery slice.
- Models: the session and every subagent run on Opus. `.claude/settings.json`
  sets `model` and `CLAUDE_CODE_SUBAGENT_MODEL`; never pass a smaller model to
  the Agent tool for implementation or review work.
- Everything in English: code, comments, docs, commits, UI copy.
- Simplicity is a requirement: 15 readable lines beat 30 clever ones, use
  libraries the way their docs recommend, one responsibility per file, no
  abstraction for a single caller. Check `context7` or official docs for
  version-sensitive APIs (LangChain, Langfuse, typesafe-sdk, Next.js, shadcn).
- Do not reuse code, prompts or domain logic from Raul's former employer's
  repos. Generic conventions only.

## Commands

Python API lives in `apps/api` (uv, Python 3.12). Web in `apps/web` (npm).

```bash
cd apps/api && uv sync --group dev          # install
cd apps/api && uv run task test             # unit tests (no DB, no network)
cd apps/api && uv run task test-integration # needs local Supabase + .env
cd apps/api && uv run task lint             # ruff check + format check
cd apps/api && uv run task api              # FastAPI on :8000
cd apps/api && uv run finance import <pdf>  # CLI import
supabase start && supabase db reset         # local Postgres with migrations
cd apps/web && npm run dev                  # Next.js on :3000
```

## Boundaries

- Secrets only in the repo-root `.env` (git-ignored). Never print, log or
  commit them. `.env.example` documents the keys.
- `data/raw/` holds real bank statements and is git-ignored. Read only headers
  and a few rows when inspecting; never copy contents into tests or docs. Test
  fixtures are short synthetic text with fake IBANs and names.
- jev (`typesafe-sdk`) is used only where the spec says: transaction
  categorization and the chat router. Deterministic code for dedup, transfer
  pairing, SQL safety, aggregations.
- Pydantic models at every API boundary; SQL migrations in
  `supabase/migrations`; the agent's SQL tool uses the read-only role.
- Langfuse tracing on every agent and jev call from the first implementation.

## Git

- Author: `Raul Vazquez <raul.91295@gmail.com>` (set in this repo's config).
- Remote is the personal account `raulvazquez7`; the active `gh` account is a
  different one. Push with:
  `git -c credential.helper='!f() { echo username=raulvazquez7; echo password=$(gh auth token -u raulvazquez7); }; f' push`
- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
