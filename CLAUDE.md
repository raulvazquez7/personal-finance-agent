# personal-finance-agent — Claude Code context

Project layer on top of `~/.claude/CLAUDE.md`. Raul is the engineering lead;
follow the joint-decision loop for anything not already in the spec or plan.

## What this is

Open-source, local-first personal finance assistant. Bank PDF statements are
imported into Supabase Postgres, categorized through a cascade (rules → jev →
human review), shown in Next.js dashboards, and queryable through a LangChain
agent over a semantic layer. Design: `docs/superpowers/specs/`. Plans:
`docs/superpowers/plans/`. Ideas not yet designed: `docs/backlog.md`. Read the
spec before touching architecture.
Money rules (what counts as income, spending, transfers): `docs/money-rules.md`.

## Workflow

- Always work with Superpowers in this repository, small tasks included: start
  with `superpowers:brainstorming` (name the path: spike, bounded or
  architectural, and wait for Raul's yes), then spec → plan → subagent-driven
  development with reviewers, TDD, verification before claiming done. One plan
  per delivery slice.
- Prefer subagent-driven development whenever the slice can be split into
  independent tasks and that split is worth it.
- Spec and plan usually live in one chat; implementation starts in a fresh
  context. Keep a small change in the same chat when a new context would only
  add friction.
- On Grok 4.7, hand off to a new chat with a clean context when the session
  reaches or nears 500K tokens.
- Models: the session and every subagent run on Grok 4.7 Extra High. `.claude/settings.json`
  sets `model`; never pass a smaller model to the Agent tool for implementation or review work.
- Everything in English: code, comments, docs, commits, UI copy.
- Simplicity is a requirement: 15 readable lines beat 30 clever ones, use
  libraries the way their docs recommend, one responsibility per file, no
  abstraction for a single caller.
- Before writing version-sensitive library code, read the current docs through
  Context7, or the official docs when Context7 has no page. Match the
  library's documented practice (LangChain, Langfuse, typesafe-sdk, Next.js,
  shadcn, the AI SDK, and whatever else the change touches).
- When an implementation changes something a person can see or operate, verify
  that flow with [agent-browser](https://github.com/vercel-labs/agent-browser)
  before claiming it works. Load `agent-browser skills get core` first. Open
  the page, do the action, and read the result back. A first-render screenshot
  is not the check.
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
cd apps/api && uv run finance seed          # taxonomy + system rules into the DB
cd apps/api && uv run finance categorize [--all]              # pairing, rules, jev
cd apps/api && uv run finance categorize --all --rules-only   # pairing and rules only, no jev spend
cd apps/api && uv run finance eval-categorization --note "..." # benchmark (jev spend)
cd apps/api && uv run finance labels export|import            # golden set as CSV
cd apps/api && uv run finance chat ["question"] [--thread ID]   # the chat agent in the terminal (xAI spend)
supabase start && supabase db reset         # local Postgres with migrations
cd apps/web && npm run dev                  # Next.js on :3000
```

Never run `supabase db reset` without `uv run finance labels export` first: the
reset wipes the labels (the golden set), your notes and the merchant defaults;
the CSV keeps labels and notes, not the defaults. To restore (from `apps/api`):
`finance seed`, re-import the statements with `TYPESAFE_API_KEY=` (empty: no
paid categorize run), `finance labels import ../../data/labels/<file>.csv`,
then `finance categorize`.

## Verifying the web app

Use `agent-browser` (global CLI and skill; `brew install agent-browser`) to
check the UI as a user would.
Run the API and web first; pages live at `http://localhost:3000` (`/`, `/spending/<group>`,
`/income`, `/merchants/<id>`, `/transactions`, `/subscriptions`, `/chat`, `/chat/<id>`, `/review`,
`/imports`, `/settings`).

- Before claiming an implementation that changes a user-visible flow is done:
  check that flow with `agent-browser skills get core` (open, snapshot, act,
  re-snapshot), e.g. upload a PDF on `/imports` and read the counts.
- Once per slice, before merge: one `agent-browser skills get dogfood` pass
  over the whole app, report in `dogfood-output/`.
- Pass absolute paths to `upload` and `screenshot`: the daemon does not share
  your working directory, and a relative upload path hung the page.
- Use a named session, stay on localhost, and `close` when done. Screenshots
  show real bank data: `dogfood-output/` is git-ignored, never commit captures.
- CI stays lint, type-check and build; Playwright smoke tests are v2.
- Checks that write data (labels, notes, merchant defaults, renames, imports) run on a scratch
  copy of the database, never on the real one: the recipe is "R2" in
  `docs/superpowers/plans/2026-09-25-slice-3b-interface.md`.
- Chat checks run on scripted models, never on paid ones: the API from
  `apps/api/tests/scripted_chat_server.py` on a scratch copy of the database, recipe "R3" in
  `docs/superpowers/plans/2026-10-12-slice-4b-chat-web.md`.

## Boundaries

- Secrets only in the repo-root `.env` (git-ignored). Never print, log or
  commit them. `.env.example` documents the keys.
- `data/raw/` holds real bank statements and is git-ignored. Read only headers
  and a few rows when inspecting; never copy contents into tests or docs. Test
  fixtures are short synthetic text with fake IBANs and names.
- jev (`typesafe-sdk`) is used only for transaction categorization; the chat
  agent is an LLM (grok) over the semantic layer. Deterministic code for dedup,
  transfer pairing, SQL safety, aggregations.
- The product chat agent stays LangGraph in `apps/api`. The AI SDK
  (`useChat`) is only the browser transport.
- The chat agent reads only the `agent` schema, as `agent_reader` in a
  read-only transaction; never widen its grants.
- Pydantic models at every API boundary; SQL migrations in
  `supabase/migrations`; the agent's SQL tool uses the read-only role.
- Langfuse tracing on every agent and jev call from the first implementation.

## Git

- Author: `Raul Vazquez <raul.91295@gmail.com>` (set in this repo's config).
- Remote is the personal account `raulvazquez7`; the active `gh` account is a
  different one. Push with:
  `git -c credential.helper='!f() { echo username=raulvazquez7; echo password=$(gh auth token -u raulvazquez7); }; f' push`
- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).

<!-- OPENWIKI:START -->

## OpenWiki

@AGENTS.md

<!-- OPENWIKI:END -->
