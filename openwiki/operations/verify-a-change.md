---
type: operations
title: Verify a change
description: Which command matches a change, what CI actually runs, and which checks do not count as CI.
tags: [verification, ci, tests, lint]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-17T19:58:49.962Z
sources:
  - id: openwiki-source-164e2da859b5277df81c7d94
    resource: repo://.github/workflows/ci.yml
  - id: openwiki-source-21e28a8767f951c69667a0ed
    resource: repo://apps/api/finance/db.py
  - id: openwiki-source-b2697db94ca37e702a50682a
    resource: repo://apps/api/pyproject.toml
  - id: openwiki-source-3a2dde6adaa0b4f58984ea0b
    resource: repo://apps/api/tests/conftest.py
  - id: openwiki-source-e791ccf0b82a013c89a960ec
    resource: repo://apps/api/tests/scripted_chat_server.py
  - id: openwiki-source-029ae4ff644f10760accffe0
    resource: repo://apps/api/tests/test_jev_client.py
  - id: openwiki-source-4baf186d721e28b7a95fa5dc
    resource: repo://apps/api/tests/test_pairing.py
  - id: openwiki-source-2266554e08129681aa07c138
    resource: repo://apps/api/tests/test_views.py
  - id: openwiki-source-99de51df25f29bfc72caf823
    resource: repo://apps/web/package.json
  - id: openwiki-source-bbd53ba6601341ffa125390c
    resource: repo://apps/web/tsconfig.json
  - id: openwiki-source-7abd17491f1f93f66d6b768e
    resource: repo://apps/web/vitest.config.mts
  - id: openwiki-source-a2371d6362e5db4bc834ad03
    resource: repo://CLAUDE.md
generated: { by: "openwiki/0.7.2", at: "2026-10-17T19:58:49.962Z" }
---

# Verify a change

Match the change to a command, run that command, and name it when you say the change is verified. A green unit run does not cover a view, a route the browser paints, or a write. CI is narrower than the local suite.

Related: [Configuration](configuration.md) for settings checks, [Ask a question](../workflows/ask-a-question.md), [Import to dashboard](../workflows/import-to-dashboard.md), [Review and labels](../workflows/review-and-labels.md), and [Run categorization eval](../workflows/run-categorization-eval.md) for the flows those checks lock.

## What CI runs

CI is `.github/workflows/ci.yml`. It runs on every push to `main` and on every pull request. Two jobs, both on `ubuntu-latest`. Neither job starts Supabase, Playwright, or a browser.

| Job | Working directory | Setup | Commands |
| --- | --- | --- | --- |
| `api` | `apps/api` | `astral-sh/setup-uv@v5` with cache, then `uv sync --group dev` | `uv run task lint`, then `uv run task test` |
| `web` | `apps/web` | Node 22, npm cache on `apps/web/package-lock.json`, then `npm ci` | `npm run lint`, then `npm run build` |

The OpenWiki update workflow is a separate scheduled job. It does not lint or test this repository.

```mermaid
flowchart TD
    change["kind of change"] --> apiUnit{"Python logic, no live database?"}
    apiUnit -->|yes| unit["uv run task test"]
    apiUnit -->|no| apiDb{"SQL, views, or a route that opens the pool?"}
    apiDb -->|yes| integ["uv run task test-integration"]
    change --> pyStyle{"Python style or imports?"}
    pyStyle -->|yes| lint["uv run task lint"]
    change --> webLib{"Pure helper under apps/web/src/lib?"}
    webLib -->|yes| vitest["npm run test"]
    change --> webShip{"Web lint, types, or a production bundle?"}
    webShip -->|yes| webCi["npm run lint and npm run build"]
    change --> ui{"A person can see or operate it?"}
    ui -->|read only| browser["agent-browser on the running app"]
    ui -->|writes labels, notes, defaults, renames, or imports| r2["recipe R2, scratch database"]
    ui -->|chat UI| r3["recipe R3 and scripted_chat_server"]
    unit --> ci["CI api job"]
    lint --> ci
    webCi --> ciWeb["CI web job"]
    integ --> notCi["not CI"]
    vitest --> notCi
    browser --> notCi
    r2 --> notCi
    r3 --> notCi
```

CI is the `api` lint and unit-test job and the `web` lint and build job. Integration tests, vitest, and agent-browser are not on that path.

## API commands

All of these run from `apps/api`. Taskipy defines them in `apps/api/pyproject.toml`. `uv sync --group dev` installs pytest, httpx, ruff, and taskipy. CI does that before lint and test.

| Command | What it runs | Needs |
| --- | --- | --- |
| `uv run task test` | `pytest -m "not integration"` | Nothing live. No database and no network. |
| `uv run task lint` | `ruff check . && ruff format --check .` | The dev group. Check only. It does not rewrite files. |
| `uv run task test-integration` | `pytest -m integration` | Local Supabase and the repo-root `.env`. Not CI. |
| `uv run task format` | `ruff format . && ruff check --fix .` | A local rewrite. CI never runs this. |

Pytest uses `tests` as `testpaths`, `-q`, and `--strict-markers`. The only marker is `integration`: needs a local Supabase database and the repo-root `.env`. An unknown marker fails collection. `uv run task test` and `uv run task test-integration` are disjoint. A file can carry both kinds of test. `test_pairing.py`, `test_loans.py`, `test_store.py`, `test_importer.py`, `test_taxonomy.py`, `test_jev_client.py`, and `test_chat_api.py` do. Deselecting the marker skips the live cases and still runs the rest. A whole-file `pytestmark = pytest.mark.integration` (`test_views.py`, `test_schema.py`, `test_db.py`, `test_eval_run.py`, and the other dashboard and agent-view files) never runs under `task test`.

`db_conn` opens `finance.db.connection()`, which reads `SUPABASE_DB_URL` through `get_settings()` and raises if it is unset. The fixture wraps the connection in `transaction(force_rollback=True)`, so rows that fixture writes are rolled back when the test ends. That is not a license to point a writing check at the real database. See scratch copies below.

`conftest.py` sets `LANGFUSE_TRACING_ENABLED=false` unless `RUN_LIVE_JEV=1`, so a normal run exports no traces. The only live jev test is `test_real_jev_answers_a_synthetic_question` in `tests/test_jev_client.py`. It is marked `integration` and still skips unless `RUN_LIVE_JEV=1`. It spends money. Do not set that variable to make `task test-integration` green.

`raw_pdfs` skips when `data/raw` has no PDFs. `test_real_statements_import_once_and_never_twice` is the integration test that uses it. It is not part of `task test`, and it does not run in CI.

Ruff selects `E`, `F`, `I`, `UP`, and `B`, line length 100, target Python 3.12. `fastapi.Query`, `fastapi.Depends`, `typer.Argument`, and `typer.Option` are allowed in defaults. A lint failure is a CI failure even when tests pass.

## Web commands

From `apps/web`, after `npm ci` (what CI runs) or a local `npm install`:

| Command | What it runs | CI? |
| --- | --- | --- |
| `npm run lint` | `eslint`, with `eslint-config-next` core-web-vitals and TypeScript | Yes |
| `npm run build` | `next build` | Yes. This is the type check. `tsconfig.json` is `strict` and `noEmit`. There is no `typecheck` script. |
| `npm run test` | `vitest run` | No |
| `npm run dev` | `next dev` on port 3000 | No. Needed before an agent-browser pass. |
| `npm run gen:api` | Regenerates `src/lib/api-types.ts` from `http://localhost:8000/openapi.json` | No. The API must already be running. |

Vitest is configured in `apps/web/vitest.config.mts`. Environment is `node`. Include is `src/**/*.test.ts`. `TZ` is `America/Los_Angeles` before any module loads, so date helpers are tested west of UTC. Components are not in this run. There is no jsdom and no React Testing Library. A component or page change is not verified by `npm run test`.

`npm run build` is the check that the production bundle type-checks. `npm run lint` does not compile the app. Run both when the change touches `apps/web` the way CI does. Run `npm run test` as well when the change touches a helper under `src/lib`.

## Match the change to a check

Name the command that actually ran. Do not treat a neighboring check as coverage.

| You changed | Run | Does not verify it |
| --- | --- | --- |
| Python unit logic, parsers, the SQL guard, YAML shape, settings | `cd apps/api && uv run task test` | A skipped `integration` test in the same file |
| Python style or import order | `cd apps/api && uv run task lint` | `task test` |
| A migration, a view, `agent_reader`, or a route that opens the pool | `cd apps/api && uv run task test-integration` against local Supabase | `task test`, and CI |
| A pure helper in `apps/web/src/lib` | `cd apps/web && npm run test` | `npm run lint` or `npm run build` alone |
| Web components, routes, or generated API types | `cd apps/web && npm run lint` and `npm run build` | Vitest, unless a `src/lib` helper changed too |
| A user-visible flow | agent-browser against the running API and web, as below | A first-render screenshot, Playwright, or CI |
| Labels, notes, merchant defaults, renames, or imports from the UI | Recipe R2, then agent-browser | The real database |
| The chat UI | Recipe R3 and `tests.scripted_chat_server` | A paid model, and CI |

Focused files, when the change is narrow:

- Settings and host or origin checks: `tests/test_settings.py`, `tests/test_api.py`. The 503 when chat is unset is the unit test in `tests/test_chat_api.py`, not the marked streaming tests in that file.
- Ingestion: `tests/test_importer.py`, `tests/test_dedup.py`. The real-PDF import case is integration-only.
- Cascade: `tests/test_pairing.py`, `tests/test_rules.py`, `tests/test_categorizer.py`, `tests/test_jev_questions.py`, `tests/test_merchants.py`, `tests/test_store.py`, `tests/test_loans.py`. Pairing, store, and loan cases that use `db_conn` are integration.
- Money views: `tests/test_views.py` and `tests/test_breakdowns.py` (integration). After a view change, start the API so `validate_layer` runs. A column mismatch is a startup failure.
- Agent boundary: `tests/test_sql_guard.py` and `tests/test_agent_graph.py` under `task test`. `tests/test_catalog_db.py`, `tests/test_agent_views.py`, and `tests/test_sql_runner_db.py` under `task test-integration`.
- Categorization eval code: `tests/test_eval_metrics.py` is a unit test. `tests/test_eval_run.py` is integration and refuses a real jev client. The paid benchmark is `uv run finance eval-categorization`, not either of those.
- Web helpers: the `src/lib/*.test.ts` files, including `format.test.ts` and `chat.test.ts`.

## What is not CI

Integration tests are not CI. `task test-integration` never appears in `.github/workflows/ci.yml`. A pull request can be green with a broken view.

Playwright is not CI. The web package has no Playwright script and no Playwright dependency of its own. Browser smoke tests are not this suite.

Vitest is not CI. The web job runs lint and build only. A broken helper test does not fail the pull request until someone runs `npm run test`.

agent-browser is not CI. It is a local check against `http://localhost:3000`.

`uv run task format` is not CI. CI runs the check form, `task lint`.

## User-visible flows

CI stays lint and build for the web. A change a person can see or operate is verified with agent-browser, not with the CI job.

Run the API (`cd apps/api && uv run task api`, port 8000) and the web (`cd apps/web && npm run dev`, port 3000) first. Pages live at `http://localhost:3000`: `/`, `/spending/<group>`, `/income`, `/merchants/<id>`, `/transactions`, `/subscriptions`, `/chat`, `/chat/<id>`, `/review`, `/imports`, `/settings`.

The check is `agent-browser` (global CLI). Load `agent-browser skills get core` first. Open the page, do the action, and read the result back. A first-render screenshot is not the check. Once per slice, before merge, one `agent-browser skills get dogfood` pass covers the whole app and reports in `dogfood-output/`. Pass absolute paths to `upload` and `screenshot`. Use a named session, stay on localhost, and `close` when done. Screenshots show real bank data. `dogfood-output/` is git-ignored. Do not commit captures.

## Scratch copies

Checks that write labels, notes, merchant defaults, renames, or imports run on a scratch copy of the database, never on the real one. The recipe is **R2** in `docs/superpowers/plans/2026-09-25-slice-3b-interface.md`. [CLAUDE.md](../../CLAUDE.md) says where that recipe is. This page does not describe its steps.

Chat checks run on scripted models, never on paid ones. The API is `apps/api/tests/scripted_chat_server.py`, on a scratch copy of the database. The recipe is **R3** in `docs/superpowers/plans/2026-10-12-slice-4b-chat-web.md`. [CLAUDE.md](../../CLAUDE.md) says where that recipe is. This page does not describe its steps.

The scripted server is the process those chat checks start. It is not a pytest task. From `apps/api`:

```bash
CORS_ORIGINS='["http://localhost:3001"]' \
  uv run python -m tests.scripted_chat_server --port 8001 \
  --db-url postgresql://postgres:postgres@127.0.0.1:54322/scratch_review
```

`--db-url` is required. `is_scratch_database` parses the URL with `conninfo_to_dict` and accepts only a database name that starts with `scratch_`. Anything else, including a query string that would open `postgres`, exits with `Refusing a database whose name does not start with scratch_ (see recipe R3).` It sets `SUPABASE_DB_URL` to that URL and turns Langfuse tracing off before importing the app. `--disabled` serves the 503 of a chat with no xAI key. The unit test for the name check is `tests/test_scripted_chat_server.py`, which `task test` already runs.

`supabase db reset` is not a verification command. It wipes labels, notes, and merchant defaults. [CLAUDE.md](../../CLAUDE.md) says to export labels first.
