# Agent wiki with OpenWiki

Date: 2026-10-17
Status: draft for Raul's review
Owner: Raul Vazquez

Delivery 2 of 2. It starts after delivery 1 (`2026-10-17-public-face-design.md`) merges, so
the wiki describes the final README and architecture page. One plan, one PR.

## 1. Purpose

Coding agents working on this repo should find the architecture, the cascade, the money rules,
the chat agent and the ways to verify a change without re-reading half the tree at the start of
every session. OpenWiki generates and maintains that wiki from the repo and keeps it grounded in
the source.

The audience is agents. People get the README. The wiki must not inflate the context every
session loads. Agents should pull a page when a task needs it, not read the whole wiki up
front.

## 2. What OpenWiki is

Checked on 2026-10-17 against the current docs (Context7 `/langchain-ai/openwiki` and
docs.langchain.com/oss/openwiki/overview). Latest npm version: `0.7.2`, Node ≥ 22.22.0.

- It is a CLI built on Deep Agents. `openwiki --init` generates Markdown under `openwiki/`.
  `openwiki --update` refreshes it from the commits since the last run, and a clean update
  makes no model calls.
- **Grounding.** Each factual page has a claim sidecar under `openwiki/.claims/` that points
  to versioned source evidence. The sidecars are committed with the pages.
- **The brief.** `openwiki/INSTRUCTIONS.md` is written by us. OpenWiki reads it for scope and
  priorities and never rewrites it.
- **Read boundary.** `.openwikiignore` uses gitignore syntax. Ignored paths are never read,
  scanned or quoted. The docs say the agent may still infer an ignored area from other files.
- **Agent wiring.** On every run OpenWiki maintains its own block in `AGENTS.md`, between
  `<!-- OPENWIKI:START -->` and `<!-- OPENWIKI:END -->`. It creates the file when missing.
  When `CLAUDE.md` exists, OpenWiki adds a minimal block that only imports `@AGENTS.md`.
  Content outside the markers is left alone.
- **Retrieval-first.** The `AGENTS.md` block tells agents not to preload or enumerate the wiki.
  They search it (`openwiki_search`, `openwiki_read`) when unfamiliar architecture matters to a
  task, and fall back to `openwiki/quickstart.md` when those tools are not installed.
- **Providers.** OpenAI (default), Anthropic, OpenRouter, Gemini, Bedrock, an OpenAI-compatible
  base URL and others. Keys live in `~/.openwiki/.env`, never in the repo. `OPENWIKI_PROVIDER`
  and `OPENWIKI_MODEL_ID` select the provider and model without prompts.
- **Freshness.** A scheduled CI example (`examples/openwiki-update.yml`) runs
  `openwiki code --update --print` and opens a docs PR.

## 3. Decisions

| Topic | Call |
|---|---|
| Version | Pin `openwiki@0.7.2` (or the latest patch at execution time, recorded in the PR) and run it with `npx`, so nothing is installed globally |
| Where it runs | A fresh git worktree of the delivery-2 branch. Ignored files (`data/raw/`, `data/labels/`, `.env`, spike outputs, captures) do not exist there at all. `.openwikiignore` is the second barrier |
| Provider and model | **Open: Raul picks.** Options in section 4 |
| Brief | `openwiki/INSTRUCTIONS.md`, written before the first run (section 5) |
| Ignore list | Section 6 |
| `AGENTS.md` | Accepted. It holds only OpenWiki's managed block |
| `CLAUDE.md` | Gains only OpenWiki's minimal `@AGENTS.md` block, between markers. Nothing else changes. The plan measures the imported `AGENTS.md` block, and if it is over 40 lines, it stops and asks Raul |
| Claude Code integration | Not committed. `openwiki integrations install claude` stays a per-developer choice. Without it, agents use the `quickstart.md` fallback |
| Generated pages | Never edited by hand. A wrong page is fixed through the brief plus `--update`, or through `--init` again, at most twice. After that, the error goes to the PR description as a known issue |
| Human pages | `docs/architecture.md` "Where to read next" gains one row: the agent wiki (`openwiki/quickstart.md`). The README does not link it |
| Freshness | Manual `openwiki --update` before a slice merges. The scheduled CI job is out of scope (it needs a provider key in repo secrets and a daily spend). It goes into `docs/backlog.md` as an idea |
| Tracing | LangSmith off. OpenWiki tracing is not part of this project's Langfuse setup |

## 4. Provider options (Raul decides)

| Option | Key | For | Against |
|---|---|---|---|
| A. Anthropic | `ANTHROPIC_API_KEY` | First-class OpenWiki provider; strong at long repo reading and writing | A new key and bill, if Raul has none |
| B. OpenRouter | `OPENROUTER_API_KEY` | The provider in OpenWiki's own CI example; any model behind one key | A third party sees the repo (it is public anyway) |
| C. xAI through the OpenAI-compatible base URL | the existing `XAI_API_KEY` | No new account; same vendor as the chat | Not a documented OpenWiki path; the `openai` provider uses the Responses API. Needs a spike before trusting it |

Recommendation: A when Raul has an Anthropic key, otherwise C after a five-minute spike
(a one-shot `openwiki -p "what can you do?"`). B is the fallback. The cost of one `--init`
on this repo is unknown. Task 1 measures it on a small run and stops if the projected cost
exceeds a cap Raul sets, 5 USD by default.

## 5. The brief: `openwiki/INSTRUCTIONS.md`

Written by us, short, and the only wiki file edited by hand.

- **Audience.** Coding agents changing this repo. Practical and source-grounded, with no
  marketing.
- **Priorities, in order:**
  1. A map of the code: `apps/api` packages, `apps/web` routes, `supabase/migrations`.
  2. The categorization cascade and its thresholds.
  3. The money rules, linked to `docs/money-rules.md` as the contract and not restated.
  4. The chat agent: `create_agent`, `run_sql`, the read-only role, the semantic layer, how to
     change a metric safely.
  5. How to verify: the test tasks, scratch-database recipes R2 and R3, agent-browser.
  6. The eval workflow and how to read `HISTORY.md`.
- **Sources of truth.** Code and tests win. Specs explain why. The v1 spec section 9 (jev
  router) was superseded by slice 4 spec section 16. Plans are history, not instructions.
- **Never:**
  - personal amounts, account numbers or merchant names from anywhere;
  - describing the contents of `data/`;
  - copying the README;
  - presenting a backlog item as built.

## 6. `.openwikiignore`

```gitignore
# Secrets and personal financial data (also absent from the worktree)
.env
.env.*
!.env.example
data/
docs/superpowers/spikes/*/output/
dogfood-output/
eval-output/
# Tooling that is not this project's code
.claude/
.agents/
.superpowers/
skills-lock.json
node_modules/
apps/web/.next/
supabase/.temp/
supabase/.branches/
# Implementation plans: task-level history, superseded by code
docs/superpowers/plans/
```

Images in `docs/images/` stay readable. They are synthetic.

## 7. Files

| Path | Change |
|---|---|
| `.openwikiignore` | new |
| `openwiki/INSTRUCTIONS.md` | new, hand-written |
| `openwiki/**` and `openwiki/.claims/**` | generated |
| `AGENTS.md` | new, OpenWiki's managed block only |
| `CLAUDE.md` | OpenWiki's minimal block only |
| `docs/architecture.md` | one row in "Where to read next" |
| `docs/backlog.md` | one idea: the scheduled `openwiki --update` job |

## 8. Verification

- **Privacy.**
  - `git grep -nE 'ES[0-9]{22}'` over `openwiki/` finds only `ES00…` test fakes.
  - Every euro amount the wiki prints is either a test-fixture number or a figure from
    `HISTORY.md`. A reviewer subagent lists them all.
  - No page describes the contents of `data/`.
- **Facts.** A reviewer subagent samples the pages on the cascade, the chat and the money rules
  and checks each claim against the code and the claim sidecars. It confirms that no page
  describes a jev router as built.
- **Context cost.** The `CLAUDE.md` diff is the managed block and nothing else. The `AGENTS.md`
  block is no more than 40 lines and tells agents not to preload the wiki.
- **Stability.** A second `openwiki --update` right after the first is a no-op: no model calls
  and no page diffs.
- **Agent check.** A fresh Claude Code session in the worktree is asked one architecture
  question ("where is the 0.95 threshold applied and why?"). It answers from the wiki or the
  code without reading the whole wiki.
- **Review.** SDD's per-task reviews, then a final whole-branch review before the PR.

## 9. Out of scope

- The scheduled CI update job (it becomes a backlog idea)
- A personal-mode wiki, `openwiki visualize` exports or GitHub Pages
- Committing the Claude Code integration
- Hand-editing generated pages

## 10. Success

- `openwiki/` is committed and grounded, with sidecars, and gives agents a quickstart.
- `CLAUDE.md` only gained the managed import.
- A no-op update stays clean.
- The wiki carries no personal data and describes the chat as the ReAct agent that shipped.
