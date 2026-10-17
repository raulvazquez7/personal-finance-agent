# Brief for the tally ai repository wiki

## Audience

Coding agents changing this repository. Write practical, source-grounded pages: where things
live, why they are built that way, and how to verify a change. No marketing. People read the
README instead.

## Priorities, in order

1. A map of the code: the `apps/api/finance` packages (ingestion, categorization, dashboard,
   agent, evals, api), the `apps/web/src/app` routes, and `supabase/migrations`.
2. The categorization cascade: own-account pairing, system rules, jev (one call with three
   typed questions), merchant resolution, merchant defaults, the 0.95 review threshold, and
   `link_loans`.
3. The money rules. `docs/money-rules.md` is the contract: link it, do not restate it.
4. The chat agent: `create_agent` with the single `run_sql` tool, the `agent` schema and the
   `agent_reader` role, the sqlglot guard, the YAML semantic layer and its startup check, the
   checkpointer, and how to change a metric or an example safely.
5. How to verify a change: `uv run task test`, `task lint`, `task test-integration`, the
   scratch-database recipes R2 and R3, and agent-browser for UI flows.
6. The categorization eval: `finance eval-categorization`, and how to read
   `docs/evals/HISTORY.md` (the golden set changed between lines; noise is about ten rows).

## Sources of truth

- Code and tests win over every document.
- Specs in `docs/superpowers/specs/` explain why. The v1 spec's section 9 (a jev router in front
  of the chat) was superseded by the slice 4 spec's section 16: the shipped chat is one ReAct
  agent with no router.
- `docs/backlog.md` lists ideas that are not built. Never present one as existing.
- `CLAUDE.md` holds the working rules. Do not repeat them.

## Never

- Write personal amounts, account numbers, IBANs or merchant names from any source. Use only
  the metrics in `docs/evals/HISTORY.md` and numbers from test fixtures.
- Describe the contents of `data/` or of any ignored path.
- Copy the README or `docs/architecture.md`. Link them.
