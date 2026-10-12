# Slice 4a — Chat Agent Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A chat agent that answers questions about the user's own bank data by writing read-only SQL over a described data model, keeps every conversation in Supabase Postgres, streams its answers in the AI SDK protocol and is traced in Langfuse, usable from the API and from `finance chat`.

**Architecture:** One LangChain `create_agent` ReAct loop with one tool, `run_sql`, that runs guarded SELECTs as the no-login role `agent_reader` inside a read-only transaction over the `agent` schema (two views over the slice 3 views). A static instructions file and a per-turn data context (YAML semantic layer + values and coverage read from the database + today) are joined into the system message on every model call. LangGraph's `AsyncPostgresSaver` holds the agent's memory; `chat_threads` and `chat_messages` hold what the user sees. A `ChatService` runs each turn in its own task and relays AI SDK UI message stream parts to FastAPI and the CLI.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic v2, psycopg 3 (async pool), Supabase Postgres 17, LangChain 1.4 (`create_agent`, built-in middleware), LangGraph 1.2 (`AsyncPostgresSaver`), `langchain-xai` (grok-4.7), sqlglot, Langfuse 4, pytest, Typer.

**Spec:** `docs/superpowers/specs/2026-10-12-slice-4-chat-design.md`. Read sections 1-9, 11-16 and the "Plan 4a amendments" in section 16 before starting. The v1 spec (`2026-09-22-personal-finance-agent-v1-design.md`) and the slice 3 spec are the baseline it amends.

**How this plan was validated:** every file below was written and run on 2026-10-12 in a copy of the repo against a scratch Supabase Postgres 17.6 container with the pinned libraries (langchain 1.4.4, langgraph 1.2.14, langgraph-checkpoint-postgres 3.1.2, langchain-xai 1.3.0, sqlglot 30.22, langfuse 4.17): 326 unit and 127 integration tests passed, ruff clean, and one live turn with `grok-4.7` answered correctly end to end. Copy the code as written; if a library behaves differently, stop and report instead of improvising.

## Global Constraints

- Everything in English: code, comments, docs, commits, UI copy.
- Simplicity is a requirement: plain functions, one responsibility per file, no abstraction for a single caller. Follow the existing style; never build SQL from user input (the agent's SQL goes through the guard and the read-only role).
- Do not reuse code, prompts or domain logic from Raul's former employer's repos (Simon). Nothing in this plan comes from there.
- Commands run from `apps/api`: `uv run task test` (unit), `uv run task test-integration` (local Supabase + repo-root `.env`), `uv run task lint`. Run `uv run task format` before `uv run task lint`; `ruff format` does not split long string literals, split SQL strings over 100 characters by hand.
- Async tests follow the repo convention: plain test functions that call `asyncio.run(...)`. Do not add pytest-asyncio or anyio markers.
- **Never run `supabase db reset`.** Apply the new migration with `supabase migration up` from the repo root, after `uv run finance labels export` (it refuses to overwrite; that is fine).
- Integration tests: ledger rows only through `db_conn` (rolled back), dates in 1999, fake IBANs, `ZZTEST` text. Chat integration tests open the chat with scripted models (`tests/fakes.py`), create their own threads and delete them (rows and checkpoints) before they end; they never write ledger rows.
- No test calls a paid model: scripted models only. Live model calls happen in Task 15 only, with Raul's explicit approval. `tests/conftest.py` already disables Langfuse export in tests.
- The repo is public: no real amounts, merchants, account digits or statement names in code, tests, docs, commits or PR text.
- Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`), no attribution trailer. Git author is configured in the repo. Push with the command in `CLAUDE.md`.
- After an API model change, regenerate the web types: `cd apps/web && npm run gen:api` with the API running on :8000 (Task 14).

## Review Focus

The inputs and conditions the spec implies that a person will meet, each pinned by a test in the task that owns the code:

1. **The browser disconnects before reading a single part** (closed tab right after sending). The turn must still finish, save its answer and free the thread. Test: Task 11 `test_a_turn_nobody_reads_still_finishes_saves_and_frees_the_thread`.
2. **The model sends its text as content blocks instead of a string** (a provider change; Simon lost whole answers to this). The text must still stream. Test: Task 9 `test_text_sent_as_content_blocks_is_streamed_as_text`.
3. **A fresh install with no statements imported** (new open-source user). The data context must say nothing is imported, not crash. Test: Task 6 `test_an_empty_ledger_says_nothing_is_imported_yet`.
4. **A query whose columns share a name** (`SELECT 1 AS n, 2 AS n`, easy for a model to write). Both columns must survive. Test: Task 4 `test_columns_with_the_same_name_are_all_kept`.
5. **Deleting a chat while it is answering** (two tabs). Must answer 409, never delete the checkpoint under a running turn. Test: Task 12 `test_a_chat_cannot_be_deleted_while_it_answers`.

## File Structure

| File | Responsibility |
|---|---|
| `supabase/migrations/20261012000000_slice4_chat.sql` | schema `agent`, its two views, role `agent_reader`, `chat_threads`, `chat_messages` |
| `apps/api/finance/settings.py` | the nested `chat` settings group; drop the read-only URL |
| `apps/api/finance/db.py` | `async_pool()` for the chat |
| `apps/api/finance/agent/models.py` | `QueryResult`, `Thread`, `ChatMessage` (shared with the API) |
| `apps/api/finance/agent/sql_guard.py` | one read-only SELECT over the agent views |
| `apps/api/finance/agent/sql_runner.py` | run a guarded query as `agent_reader`; errors as data; `explain` |
| `apps/api/finance/agent/semantic/*.yaml` | model knowledge and attributes, metrics, query examples |
| `apps/api/finance/agent/semantic_layer.py` | load and check the YAML |
| `apps/api/finance/agent/catalog.py` | column types, taxonomy, accounts with coverage; startup validation |
| `apps/api/finance/agent/data_context.py` | render the per-turn data context |
| `apps/api/finance/agent/prompts/system.md`, `summary.md` | instructions; summarization prompt |
| `apps/api/finance/agent/prompt.py` | load prompts; the two-block system message |
| `apps/api/finance/agent/tools.py` | `run_sql` tool and its compact table |
| `apps/api/finance/agent/middleware.py` | middleware stack and three small hooks |
| `apps/api/finance/agent/graph.py` | `AgentContext`, `ChatModels`, `build_agent` |
| `apps/api/finance/agent/ui_stream.py` | agent stream → AI SDK UI message stream parts; SSE encoding |
| `apps/api/finance/agent/store.py` | threads and messages |
| `apps/api/finance/agent/title.py` | chat title with fallback |
| `apps/api/finance/agent/service.py` | one turn end to end: stream, persistence, title, Langfuse |
| `apps/api/finance/agent/runtime.py` | `open_chat()`: pool, validation, checkpointer, agent |
| `apps/api/finance/agent/cli.py` | `finance chat` session and rendering |
| `apps/api/finance/api/chat.py`, `main.py` | chat routes; app lifespan |
| `apps/api/finance/cli.py` | the `chat` command |
| `README.md`, `CLAUDE.md`, `.env.example`, `docs/backlog.md` | docs (Task 14) |

---

### Task 1: Dependencies and the `chat` settings group

**Files:**
- Modify: `apps/api/pyproject.toml`, `apps/api/uv.lock` (through `uv add`)
- Modify: `apps/api/finance/settings.py` (whole file below)
- Modify: `.env.example`
- Test: `apps/api/tests/test_settings.py`

**Interfaces:**
- Produces: `finance.settings.ChatSettings` (fields in spec section 12) and `Settings.chat`; `Settings` reads `CHAT__<FIELD>` from the environment (`env_nested_delimiter="__"`); `ReasoningEffort = Literal["low", "medium", "high", "xhigh"]`. `Settings.supabase_db_url_readonly` is removed.

- [ ] **Step 1: Write the failing tests**

In `apps/api/tests/test_settings.py`, delete the line `    "supabase_db_url_readonly",` from `SECRETS`, and append:

```python
def test_chat_defaults_follow_the_spec():
    chat = Settings(_env_file=None).chat
    assert (chat.model, chat.reasoning_effort) == ("xai:grok-4.7", "high")
    assert (chat.summary_model, chat.summary_reasoning_effort) == ("xai:grok-4.7", "medium")
    assert chat.title_model == "xai:grok-4.20-non-reasoning"
    assert chat.summary_trigger_tokens == 150_000


def test_chat_settings_come_from_nested_env_variables(monkeypatch):
    monkeypatch.setenv("CHAT__REASONING_EFFORT", "medium")
    monkeypatch.setenv("CHAT__MAX_SQL_CALLS_PER_TURN", "5")
    chat = Settings(_env_file=None).chat
    assert (chat.reasoning_effort, chat.max_sql_calls_per_turn) == ("medium", 5)


def test_an_unknown_reasoning_effort_is_rejected():
    with pytest.raises(ValidationError, match="reasoning_effort"):
        Settings(_env_file=None, chat={"reasoning_effort": "extreme"})


def test_model_calls_must_leave_room_for_the_answer():
    # With as many model calls as queries, the last query's result would never be answered.
    with pytest.raises(ValidationError, match="max_model_calls_per_turn"):
        Settings(_env_file=None, chat={"max_sql_calls_per_turn": 8, "max_model_calls_per_turn": 8})
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_settings.py -q`
Expected: FAIL (`'Settings' object has no attribute 'chat'`).

- [ ] **Step 3: Add the dependencies**

Run: `uv add "langchain>=1.4.4" "langgraph>=1.2.14" "langgraph-checkpoint-postgres>=3.1.2" "langchain-xai>=1.3.0" "sqlglot>=30.22"`
Expected: `pyproject.toml` lists the five packages under `dependencies`, and `uv.lock` is updated.

- [ ] **Step 4: Replace `apps/api/finance/settings.py`**

```python
"""Application settings, read once from the repo-root .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

ReasoningEffort = Literal["low", "medium", "high", "xhigh"]


class ChatSettings(BaseModel):
    """The chat agent's knobs (slice 4 spec, section 12). Override any of them from .env with
    CHAT__<FIELD>, for example CHAT__REASONING_EFFORT=medium."""

    model: str = Field(default="xai:grok-4.7", description="Agent model, as provider:model")
    reasoning_effort: ReasoningEffort = "high"
    summary_model: str = "xai:grok-4.7"
    summary_reasoning_effort: ReasoningEffort = "medium"
    title_model: str = Field(
        default="xai:grok-4.20-non-reasoning",
        description="A model without reasoning for chat titles (provisional choice)",
    )
    max_retries: int = Field(default=2, ge=0, le=5, description="Model client retries on 429/5xx")
    summary_trigger_tokens: int = Field(default=150_000, ge=10_000)
    summary_keep_messages: int = Field(default=20, ge=2)
    clear_tool_results_trigger_tokens: int = Field(default=15_000, ge=1_000)
    clear_tool_results_keep: int = Field(default=4, ge=1)
    max_sql_calls_per_turn: int = Field(default=8, ge=1, le=30)
    max_model_calls_per_turn: int = Field(default=12, ge=2, le=60)
    recursion_limit: int = Field(default=60, ge=10, le=500, description="Backstop only")
    sql_timeout_seconds: int = Field(default=10, ge=1, le=60)
    sql_row_limit: int = Field(default=200, ge=1, le=5_000)
    sql_rows_shown: int = Field(default=50, ge=1, le=500)
    sql_max_chars: int = Field(default=8_000, ge=500, le=100_000)
    title_max_chars: int = Field(default=60, ge=20, le=200)
    user_id: str = Field(default="local", description="Langfuse user id")

    @model_validator(mode="after")
    def _limits_fit_together(self) -> Self:
        # Each query needs a model call before it, and the answer needs one more.
        if self.max_model_calls_per_turn <= self.max_sql_calls_per_turn:
            raise ValueError("max_model_calls_per_turn must be above max_sql_calls_per_turn")
        if self.sql_rows_shown > self.sql_row_limit:
            raise ValueError("sql_rows_shown cannot be above sql_row_limit")
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", extra="ignore", env_nested_delimiter="__"
    )

    # Secrets stay out of repr, so a failing assert or a log line never prints them.
    supabase_db_url: str | None = Field(default=None, repr=False)
    typesafe_api_key: str | None = Field(default=None, repr=False)
    xai_api_key: str | None = Field(default=None, repr=False)
    langfuse_public_key: str | None = Field(default=None, repr=False)
    langfuse_secret_key: str | None = Field(default=None, repr=False)
    langfuse_base_url: str = "https://cloud.langfuse.com"
    cors_origins: list[str] = ["http://localhost:3000"]
    # TestClient sends Host: testserver.
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    transfer_pattern: str = "TRASPASO|TRANSFER|BIZUM|TRF"
    transfer_window_days: int = 2
    jev_concurrency: int = Field(default=8, ge=1)
    category_threshold: float = 0.95
    brand_threshold: float = 0.5
    merge_threshold: float = 0.8
    merge_suggestion_floor: float = 0.5
    subscription_threshold: float = 0.7
    chat: ChatSettings = ChatSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Update `.env.example`**

Delete the line `SUPABASE_DB_URL_READONLY=`. After the `XAI_API_KEY=` line, add:

```
# Chat agent (slice 4). Defaults live in apps/api/finance/settings.py (ChatSettings);
# override any of them here, for example:
# CHAT__MODEL=xai:grok-4.7
# CHAT__REASONING_EFFORT=high          # low, medium, high, xhigh
# CHAT__SUMMARY_REASONING_EFFORT=medium
# CHAT__TITLE_MODEL=xai:grok-4.20-non-reasoning
# CHAT__MAX_SQL_CALLS_PER_TURN=8
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_settings.py -q && uv run task test`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/finance/settings.py apps/api/tests/test_settings.py .env.example
git commit -m "feat: chat settings group and agent dependencies"
```

---

### Task 2: Migration — the agent schema, its role and the chat tables

**Files:**
- Create: `supabase/migrations/20261012000000_slice4_chat.sql`
- Test: `apps/api/tests/test_agent_views.py` (new, integration)

**Interfaces:**
- Produces: views `agent.transactions` (columns in the test below) and `agent.subscriptions`; role `agent_reader` (no login, `SELECT` on schema `agent` only, granted to the migrating user with `SET`); tables `chat_threads(id, title, title_source, created_at, updated_at)` and `chat_messages(id, thread_id, role, content, queries jsonb, status, feedback, langfuse_trace_id, created_at)`, messages cascade with their thread.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_agent_views.py`:

```python
from decimal import Decimal

import pytest
from psycopg import errors

from tests.money_month import money_month

pytestmark = pytest.mark.integration

TRANSACTIONS = [
    "booked_at",
    "month",
    "account",
    "bank",
    "amount",
    "direction",
    "tx_type",
    "spend",
    "income",
    "category",
    "category_group",
    "merchant",
    "bank_text",
    "bank_operation",
    "note",
    "is_subscription",
    "needs_review",
]
SUBSCRIPTIONS = [
    "merchant",
    "charges",
    "last_charge",
    "typical_amount",
    "cadence",
    "monthly_equivalent",
    "active",
]


def _as_agent(db_conn) -> None:
    db_conn.execute("set local role agent_reader")
    db_conn.execute("set local search_path = agent")


def test_agent_views_expose_only_the_documented_columns(db_conn):
    rows = db_conn.execute(
        "select table_name, column_name from information_schema.columns"
        " where table_schema = 'agent' order by table_name, ordinal_position"
    ).fetchall()
    columns: dict[str, list[str]] = {}
    for row in rows:
        columns.setdefault(row["table_name"], []).append(row["column_name"])
    assert columns == {"subscriptions": SUBSCRIPTIONS, "transactions": TRANSACTIONS}


def test_agent_transactions_keep_the_money_rules_and_never_a_null_category(db_conn, make_tx):
    money_month(db_conn, make_tx)
    _as_agent(db_conn)
    rows = db_conn.execute(
        "select category, category_group, sum(spend) as spend from transactions"
        " where account = 'test 0077' and month = '1999-01' group by 1, 2"
    ).fetchall()
    by_category = {r["category"]: (r["category_group"], r["spend"]) for r in rows}
    assert by_category["uncategorized"] == ("uncategorized", Decimal("10.00"))
    assert by_category["fashion"] == ("shopping", Decimal("120.00"))
    assert by_category["loan_received"] == ("transfer", Decimal("0"))
    assert None not in by_category


def test_agent_reader_reads_the_views_and_nothing_else(db_conn):
    _as_agent(db_conn)
    assert db_conn.execute("select count(*) as n from subscriptions").fetchone()["n"] >= 0
    with pytest.raises(errors.InsufficientPrivilege):
        db_conn.execute("select count(*) from public.accounts")


def test_deleting_a_thread_deletes_its_messages(db_conn):
    thread = db_conn.execute(
        "insert into chat_threads (title) values ('ZZTEST') returning id"
    ).fetchone()["id"]
    db_conn.execute(
        "insert into chat_messages (thread_id, role, content) values (%s, 'user', 'hi')", (thread,)
    )
    db_conn.execute("delete from chat_threads where id = %s", (thread,))
    count = db_conn.execute(
        "select count(*) as n from chat_messages where thread_id = %s", (thread,)
    ).fetchone()["n"]
    assert count == 0
```

`test 0077` is the account name `make_tx` gives the IBAN `money_month` uses.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_agent_views.py -q -m integration`
Expected: FAIL (`schema "agent" does not exist` / `relation "chat_threads" does not exist`).

- [ ] **Step 3: Write the migration**

Create `supabase/migrations/20261012000000_slice4_chat.sql`:

```sql
-- Slice 4: what the chat agent can read, and the chat tables
-- (docs/superpowers/specs/2026-10-12-slice-4-chat-design.md, sections 4 and 8).

-- The agent reads only this schema. Its views are thin projections of the slice 3 views, so the
-- money rules stay in v_transactions_enriched. Not exposed: ids, raw bank descriptions (they can
-- hold a full card number), IBANs and confidences. The Supabase Data API does not expose `agent`.
create schema agent;

create view agent.transactions as
select booked_at, month, account_name as account, bank::text as bank, amount, direction,
       tx_type, spend, income,
       coalesce(category_slug, 'uncategorized') as category,
       coalesce(level1, 'uncategorized') as category_group,
       merchant_name as merchant, bank_merchant_text as bank_text,
       bank_concept as bank_operation, note, is_subscription, needs_review
from public.v_transactions_enriched;

create view agent.subscriptions as
select merchant_name as merchant, charges, last_charge, typical_amount, cadence,
       monthly_equivalent, active
from public.v_subscriptions;

-- The API switches to this role for every agent query (SET LOCAL ROLE, read-only transaction).
-- No login and no password: one database URL for everything. Roles are cluster-wide, so a
-- re-run of the migrations finds it already there.
do $$
begin
  if not exists (select from pg_roles where rolname = 'agent_reader') then
    create role agent_reader nologin;
  end if;
end
$$;

grant usage on schema agent to agent_reader;
grant select on all tables in schema agent to agent_reader;
-- Postgres 16+ gives the creator of a role no SET right on it (createrole_self_grant is empty on
-- Supabase): grant it explicitly to the user that runs the migrations, the API's user.
grant agent_reader to current_user with inherit false, set true;

create table chat_threads (
  id            uuid primary key default gen_random_uuid(),
  title         text check (char_length(title) <= 200),
  title_source  text check (title_source in ('model', 'fallback', 'user')),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index chat_threads_updated_idx on chat_threads (updated_at desc);

-- What the user sees. The agent's own memory is the LangGraph checkpoint, which summarization
-- rewrites; this history never shrinks.
create table chat_messages (
  id                 uuid primary key default gen_random_uuid(),
  thread_id          uuid not null references chat_threads(id) on delete cascade,
  role               text not null check (role in ('user', 'assistant')),
  content            text not null,
  queries            jsonb not null default '[]',
  status             text not null default 'ok' check (status in ('ok', 'error', 'stopped')),
  feedback           text check (feedback in ('up', 'down')),
  langfuse_trace_id  text,
  created_at         timestamptz not null default now()
);

create index chat_messages_thread_idx on chat_messages (thread_id, created_at);
```

- [ ] **Step 4: Back up labels and apply it**

Run (from `apps/api`): `uv run finance labels export`
Run (from the repo root): `supabase migration up`
Expected: the migration applies with no error. Check: `psql "$SUPABASE_DB_URL" -c "begin; set local role agent_reader; select count(*) from agent.transactions; rollback;"` returns a count.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_agent_views.py -q -m integration`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/20261012000000_slice4_chat.sql apps/api/tests/test_agent_views.py
git commit -m "feat: agent schema, read-only agent role and chat tables"
```

---

### Task 3: The SQL guard

**Files:**
- Create: `apps/api/finance/agent/__init__.py` (empty), `apps/api/finance/agent/sql_guard.py`
- Test: `apps/api/tests/test_sql_guard.py`

**Interfaces:**
- Produces: `check_query(sql: str) -> str` (the query without trailing semicolons) or raises `RejectedQuery(reason: str, hint: str)`; `VIEWS = frozenset({"transactions", "subscriptions"})`.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_sql_guard.py`:

```python
import pytest

from finance.agent.sql_guard import RejectedQuery, check_query

ALLOWED = [
    "SELECT month, SUM(spend) FROM transactions GROUP BY month",
    "select merchant from transactions where note ilike '%drop%' limit 20",
    "WITH m AS (SELECT month, SUM(spend) AS s FROM transactions GROUP BY 1) SELECT * FROM m",
    "SELECT 1 UNION ALL SELECT 2",
    "SELECT merchant, string_agg(DISTINCT note, ' | ') FROM transactions GROUP BY 1",
    "SELECT m FROM generate_series(DATE '2026-01-01', DATE '2026-03-01', INTERVAL '1 month') AS m",
    "SELECT t.merchant FROM transactions t JOIN subscriptions s ON s.merchant = t.merchant",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_reads_over_the_agent_views_pass(sql):
    assert check_query(sql) == sql


def test_trailing_semicolons_and_spaces_are_dropped():
    assert check_query("  SELECT * FROM subscriptions WHERE active;; ") == (
        "SELECT * FROM subscriptions WHERE active"
    )


REJECTED = [
    ("WITH d AS (DELETE FROM transactions RETURNING *) SELECT * FROM d", "DELETE is not allowed"),
    ("UPDATE transactions SET note = 'x'", "UPDATE is not a SELECT"),
    ("SELECT 1; SELECT 2", "found 2 statements"),
    ("SELECT * FROM public.transactions", "unknown table"),
    ("SELECT * FROM accounts", "unknown table"),
    ("SELECT * FROM information_schema.tables", "unknown table"),
    ("SELECT set_config('role', 'postgres', true)", "function set_config"),
    ("SELECT pg_sleep(5)", "function pg_sleep"),
    ("SELECT * FROM dblink('x', 'select 1') AS t(a int)", "function dblink"),
    ("SELECT * FROM transactions FOR UPDATE", "LOCK is not allowed"),
    ("SET ROLE postgres", "COMMAND is not a SELECT"),
    ("COPY transactions TO STDOUT", "COPY is not a SELECT"),
    ("SELECT * FROM (", "does not parse"),
]


@pytest.mark.parametrize(("sql", "reason"), REJECTED)
def test_anything_but_one_read_is_rejected_with_a_hint(sql, reason):
    with pytest.raises(RejectedQuery) as raised:
        check_query(sql)
    assert reason in raised.value.reason
    assert raised.value.hint
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_sql_guard.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'finance.agent'`).

- [ ] **Step 3: Implement**

Create the empty `apps/api/finance/agent/__init__.py`, then `apps/api/finance/agent/sql_guard.py`:

```python
"""The first check on `run_sql`: one read-only SELECT over the agent's views.

The database is the real guarantee: every query runs as `agent_reader` in a read-only transaction
(slice 4 spec, section 4.2). This check fails early with a reason and a hint the model can act on.
It walks the whole syntax tree, so a DELETE hidden in a CTE is caught, and it never matches
keywords in the raw text, so a search for '%drop%' still works.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

VIEWS = frozenset({"transactions", "subscriptions"})

_WRITES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Command,
    exp.Copy,
    exp.Set,
    exp.Lock,
    exp.TruncateTable,
)
# set_config is the only way to change role from a SELECT; the rest read files, sleep or reach
# other servers.
_DENIED_FUNCTION_PREFIXES = ("set_config", "pg_sleep", "dblink", "pg_read", "lo_")


class RejectedQuery(Exception):
    def __init__(self, reason: str, hint: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.hint = hint


def check_query(sql: str) -> str:
    """Return the query without trailing semicolons, or raise RejectedQuery."""
    cleaned = sql.strip().rstrip(";").strip()
    try:
        statements = [s for s in sqlglot.parse(cleaned, read="postgres") if s is not None]
    except ParseError as error:
        first_line = str(error).splitlines()[0]
        raise RejectedQuery(
            f"the query does not parse: {first_line}", "Write one PostgreSQL SELECT."
        ) from error
    if len(statements) != 1:
        raise RejectedQuery(
            f"found {len(statements)} statements", "Send exactly one SELECT per call."
        )
    root = statements[0]
    if not isinstance(root, exp.Query):
        raise RejectedQuery(f"{root.key.upper()} is not a SELECT", "Only read, with one SELECT.")
    for node in root.walk():
        if isinstance(node, _WRITES):
            raise RejectedQuery(f"{node.key.upper()} is not allowed", "Only read, with one SELECT.")
    ctes = {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}
    for table in root.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            continue  # a table function such as generate_series: its name is checked below
        if table.db or table.name.lower() not in VIEWS | ctes:
            raise RejectedQuery(
                f"unknown table {table.sql(dialect='postgres')}",
                "Read only the views transactions and subscriptions, without a schema.",
            )
    for function in root.find_all(exp.Func):
        name = function.name if isinstance(function, exp.Anonymous) else function.sql_name()
        if name.lower().startswith(_DENIED_FUNCTION_PREFIXES):
            raise RejectedQuery(
                f"function {name.lower()} is not allowed", "Use ordinary SQL functions only."
            )
    return cleaned
```

sqlglot logs a warning when it parses a statement it does not know (such as `SET ROLE`) as a generic command; the guard rejects it anyway.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_sql_guard.py -q`
Expected: 21 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/agent/__init__.py apps/api/finance/agent/sql_guard.py apps/api/tests/test_sql_guard.py
git commit -m "feat: SQL guard for the chat agent"
```

---

### Task 4: Run queries as `agent_reader`

**Files:**
- Create: `apps/api/finance/agent/models.py`, `apps/api/finance/agent/sql_runner.py`
- Modify: `apps/api/finance/db.py` (whole file below)
- Test: `apps/api/tests/test_sql_runner.py` (unit), `apps/api/tests/test_sql_runner_db.py` (integration)

**Interfaces:**
- Consumes: `check_query`, `RejectedQuery` (Task 3).
- Produces:
  - `finance.db.async_pool(max_size=5)` async context manager → `AsyncConnectionPool` (autocommit, dict rows, `prepare_threshold=0`).
  - `finance.agent.models`: `QueryResult(sql, columns, rows: list[list[str | None]], row_count, truncated, duration_ms, error, hint, infra_error)`, `Thread`, `ChatMessage`, `TitleSource`, `MessageStatus`, `Feedback`.
  - `finance.agent.sql_runner`: `agent_session(pool, timeout_seconds)` (read-only transaction as `agent_reader`, `search_path = agent`, rolled back), `cell(value) -> str | None`, `failed(sql, error, timeout_seconds) -> QueryResult`, `run_query(pool, sql, *, row_limit, timeout_seconds) -> QueryResult` (never raises), `explain(pool, sql) -> str | None`.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_sql_runner.py`:

```python
from datetime import date
from decimal import Decimal

import psycopg
from psycopg import errors
from psycopg_pool import PoolTimeout

from finance.agent.sql_runner import cell, failed


def test_cells_read_as_plain_text():
    assert [cell(v) for v in (Decimal("1234.50"), date(2026, 7, 1), True, None, 3)] == [
        "1234.50",
        "2026-07-01",
        "true",
        None,
        "3",
    ]


def test_sql_mistakes_come_back_with_a_hint_for_the_model():
    result = failed("SELECT x", errors.UndefinedColumn('column "merchnt" does not exist'), 10)
    assert result.error == 'column "merchnt" does not exist'
    assert result.hint == "Use only the columns listed for that view in the data model."
    assert not result.infra_error


def test_a_division_by_zero_gets_its_own_hint_before_the_generic_data_error():
    result = failed("SELECT 1/0", errors.DivisionByZero("division by zero"), 10)
    assert result.hint == "Protect divisions with NULLIF(denominator, 0)."


def test_a_timeout_asks_for_a_lighter_query():
    result = failed("SELECT 1", errors.QueryCanceled("canceling statement"), 10)
    assert result.error == "the query took longer than 10 s"
    assert not result.infra_error


def test_an_unreachable_database_is_an_infrastructure_failure():
    for error in (psycopg.OperationalError("connection refused"), PoolTimeout("no connection")):
        result = failed("SELECT 1", error, 10)
        assert result.infra_error and result.hint is None
```

Create `apps/api/tests/test_sql_runner_db.py`:

```python
import asyncio

import pytest
from psycopg import errors

from finance.agent.sql_runner import agent_session, explain, run_query
from finance.db import async_pool

pytestmark = pytest.mark.integration


def _run(sql: str, row_limit: int = 200):
    async def go():
        async with async_pool() as pool:
            return await run_query(pool, sql, row_limit=row_limit, timeout_seconds=10)

    return asyncio.run(go())


def test_a_query_over_the_agent_views_returns_columns_and_plain_rows():
    result = _run("SELECT 'x' AS label, 2.50::numeric AS amount, DATE '1999-01-31' AS day")
    assert (result.columns, result.rows) == (
        ["label", "amount", "day"],
        [["x", "2.50", "1999-01-31"]],
    )
    assert (result.row_count, result.truncated, result.error) == (1, False, None)


def test_rows_beyond_the_limit_are_cut_and_flagged():
    result = _run("SELECT n FROM generate_series(1, 5) AS n ORDER BY n", row_limit=3)
    assert result.rows == [["1"], ["2"], ["3"]] and result.truncated


def test_a_rejected_query_never_reaches_the_database():
    result = _run("DELETE FROM transactions")
    assert result.error == "DELETE is not a SELECT" and result.hint


def test_agent_reader_cannot_read_base_tables_even_past_the_guard():
    async def go():
        async with async_pool() as pool, agent_session(pool, 10) as conn:
            await conn.execute("SELECT count(*) FROM public.transactions")

    with pytest.raises(errors.InsufficientPrivilege):
        asyncio.run(go())


def test_the_transaction_refuses_writes_even_after_a_role_escape():
    async def go():
        async with async_pool() as pool, agent_session(pool, 10) as conn:
            await conn.execute("SELECT set_config('role', 'postgres', true)")
            await conn.execute("INSERT INTO public.chat_threads (title) VALUES ('ZZTEST')")

    with pytest.raises(errors.ReadOnlySqlTransaction):
        asyncio.run(go())


def test_explain_reports_the_first_error_line():
    async def go():
        async with async_pool() as pool:
            return await explain(pool, "SELECT nope FROM transactions"), await explain(
                pool, "SELECT count(*) FROM transactions"
            )

    broken, fine = asyncio.run(go())
    assert broken == 'column "nope" does not exist' and fine is None


def test_columns_with_the_same_name_are_all_kept():
    result = _run("SELECT 1 AS n, 2 AS n")
    assert (result.columns, result.rows) == (["n", "n"], [["1", "2"]])
```

The escape test proves the defence in depth: `set_config('role', ...)` really switches back to the login role (the guard blocks it in Task 3), and the read-only transaction still refuses the write. The table is schema-qualified because the session's `search_path` is `agent`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_sql_runner.py -q`
Expected: FAIL (`No module named 'finance.agent.sql_runner'`).

- [ ] **Step 3: Implement**

Create `apps/api/finance/agent/models.py`:

```python
"""Pydantic models the chat shares with the API: query results, threads and messages."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class QueryResult(BaseModel):
    """One `run_sql` call: what the UI shows, what Langfuse records, what chat_messages keeps."""

    sql: str
    columns: list[str] = []
    rows: list[list[str | None]] = []
    row_count: int = 0
    truncated: bool = False
    duration_ms: int = 0
    error: str | None = None
    hint: str | None = None
    infra_error: bool = False


TitleSource = Literal["model", "fallback", "user"]


class Thread(BaseModel):
    id: UUID
    title: str | None
    title_source: TitleSource | None
    created_at: datetime
    updated_at: datetime


MessageStatus = Literal["ok", "error", "stopped"]
Feedback = Literal["up", "down"]


class ChatMessage(BaseModel):
    id: UUID
    thread_id: UUID
    role: Literal["user", "assistant"]
    content: str
    queries: list[QueryResult]
    status: MessageStatus
    feedback: Feedback | None
    created_at: datetime
```

Replace `apps/api/finance/db.py`:

```python
"""Postgres access: one process-level pool, dict rows, plain SQL."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from functools import lru_cache

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, ConnectionPool

from finance.settings import get_settings


def _database_url() -> str:
    url = get_settings().supabase_db_url
    if not url:
        raise RuntimeError("SUPABASE_DB_URL is not set; see .env.example")
    return url


@lru_cache
def get_pool() -> ConnectionPool:
    return ConnectionPool(
        _database_url(), min_size=1, max_size=5, kwargs={"row_factory": dict_row}, open=True
    )


@contextmanager
def connection() -> Iterator[Connection]:
    with get_pool().connection() as conn:
        yield conn


@asynccontextmanager
async def async_pool(max_size: int = 5) -> AsyncIterator[AsyncConnectionPool]:
    """The chat's async pool, bound to the running event loop. LangGraph's checkpointer needs
    autocommit, dict rows and prepare_threshold=0; the agent's queries open explicit transactions.
    """
    pool = AsyncConnectionPool(
        _database_url(),
        open=False,
        max_size=max_size,
        kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0},
    )
    await pool.open()
    try:
        yield pool
    finally:
        await pool.close()
```

Create `apps/api/finance/agent/sql_runner.py`:

```python
"""Run the agent's SQL as `agent_reader`, in a read-only transaction with a timeout.

The role reads only the `agent` views; the transaction refuses any write even if the guard missed
one (slice 4 spec, section 4.2). Failures come back as data, never as exceptions, so a tool call
always gets its answer and a thread can never be left with an unanswered call.
"""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal

import psycopg
from psycopg import AsyncConnection, errors
from psycopg.rows import tuple_row
from psycopg_pool import AsyncConnectionPool, PoolTimeout

from finance.agent.models import QueryResult
from finance.agent.sql_guard import RejectedQuery, check_query

# Order matters: a subclass comes before its parent (DivisionByZero is a DataError).
_HINTS: list[tuple[type[psycopg.Error], str]] = [
    (errors.UndefinedColumn, "Use only the columns listed for that view in the data model."),
    (errors.UndefinedTable, "Read only the views transactions and subscriptions."),
    (errors.InsufficientPrivilege, "Read only the views transactions and subscriptions."),
    (
        errors.UndefinedFunction,
        "Check the function name and argument types; cast text with ::date or ::numeric.",
    ),
    (errors.GroupingError, "Every selected column that is not aggregated goes in GROUP BY."),
    (errors.SyntaxError, "Fix the syntax: write one PostgreSQL SELECT."),
    (errors.DivisionByZero, "Protect divisions with NULLIF(denominator, 0)."),
    (errors.DataError, "Check literal values and casts; dates are 'YYYY-MM-DD'."),
]


@asynccontextmanager
async def agent_session(
    pool: AsyncConnectionPool, timeout_seconds: int
) -> AsyncIterator[AsyncConnection]:
    """A connection inside a read-only transaction as agent_reader, rolled back at the end."""
    async with pool.connection() as conn, conn.transaction(force_rollback=True):
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SET LOCAL ROLE agent_reader")
        await conn.execute("SET LOCAL search_path = agent")
        await conn.execute(f"SET LOCAL statement_timeout = {int(timeout_seconds) * 1000}")
        yield conn


def cell(value: object) -> str | None:
    """A value as the model and the UI read it: plain numbers, ISO dates, empty for NULL."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date | datetime):
        return value.isoformat()
    return str(value)


def failed(sql: str, error: Exception, timeout_seconds: int) -> QueryResult:
    """The result for a query that did not run: an error the model can act on, or infra."""
    if isinstance(error, errors.QueryCanceled):
        return QueryResult(
            sql=sql,
            error=f"the query took longer than {timeout_seconds} s",
            hint="Aggregate more or narrow the period.",
        )
    first_line = str(error).splitlines()[0] if str(error) else type(error).__name__
    if isinstance(error, psycopg.OperationalError | PoolTimeout):
        return QueryResult(sql=sql, error=first_line, infra_error=True)
    hint = next((h for kind, h in _HINTS if isinstance(error, kind)), "Try a simpler query.")
    return QueryResult(sql=sql, error=first_line, hint=hint)


async def run_query(
    pool: AsyncConnectionPool, sql: str, *, row_limit: int, timeout_seconds: int
) -> QueryResult:
    """Guard and run one query; fetch at most row_limit rows and say whether there were more."""
    started = time.perf_counter()
    try:
        cleaned = check_query(sql)
    except RejectedQuery as rejected:
        return QueryResult(sql=sql, error=rejected.reason, hint=rejected.hint)
    try:
        async with agent_session(pool, timeout_seconds) as conn:
            async with conn.cursor(row_factory=tuple_row) as cursor:
                await cursor.execute(f"SELECT * FROM ({cleaned}) AS result LIMIT {row_limit + 1}")
                columns = [column.name for column in cursor.description or []]
                fetched = await cursor.fetchall()
    except (psycopg.Error, PoolTimeout) as error:
        return failed(sql, error, timeout_seconds)
    rows = [[cell(value) for value in row] for row in fetched[:row_limit]]
    return QueryResult(
        sql=sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=len(fetched) > row_limit,
        duration_ms=round((time.perf_counter() - started) * 1000),
    )


async def explain(pool: AsyncConnectionPool, sql: str) -> str | None:
    """None when the SQL compiles as agent_reader, else the first line of the error."""
    try:
        async with agent_session(pool, timeout_seconds=10) as conn:
            await conn.execute(f"EXPLAIN {sql}")
    except psycopg.Error as error:
        return str(error).splitlines()[0]
    return None
```

Rows are fetched as tuples, not the pool's dict rows, so two columns with the same name both survive. `SET` statements take no parameters, so the timeout is formatted from an `int`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_sql_runner.py -q && uv run pytest tests/test_sql_runner_db.py -q -m integration`
Expected: 5 passed, then 7 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/db.py apps/api/finance/agent/models.py apps/api/finance/agent/sql_runner.py apps/api/tests/test_sql_runner.py apps/api/tests/test_sql_runner_db.py
git commit -m "feat: run agent queries read-only as agent_reader"
```

---

### Task 5: The semantic layer files and loader

**Files:**
- Create: `apps/api/finance/agent/semantic/transactions.yaml`, `subscriptions.yaml`, `metrics.yaml`, `examples.yaml`
- Create: `apps/api/finance/agent/semantic_layer.py`
- Test: `apps/api/tests/test_semantic_layer.py`

**Interfaces:**
- Produces: `SEMANTIC_DIR`; `Kind`, `ValueSource = Literal["accounts", "categories", "category_groups"]`; models `AllowedValue`, `Attribute`, `Model`, `Metric`, `Example(question, teaches, sql: list[str])`, `SemanticLayer(models, metrics, examples)` (all `extra="forbid"`); `SemanticLayerError`; `load_semantic_layer(directory=SEMANTIC_DIR) -> SemanticLayer` (models sorted by file name: `subscriptions`, `transactions`); `layer_version(directory=SEMANTIC_DIR) -> str` (12 hex chars); `check_layer(layer, columns: dict[str, dict[str, str]]) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_semantic_layer.py`:

```python
import pytest

from finance.agent.semantic_layer import (
    SemanticLayerError,
    check_layer,
    layer_version,
    load_semantic_layer,
)
from finance.agent.sql_guard import check_query


def _columns(layer):
    return {m.model: {a.attribute: "text" for a in m.attributes} for m in layer.models}


def test_the_yaml_loads_into_two_models_with_metrics_and_examples():
    layer = load_semantic_layer()
    assert [m.model for m in layer.models] == ["subscriptions", "transactions"]
    assert [m.name for m in layer.metrics] == [
        "expenses",
        "income",
        "savings",
        "savings_rate",
        "net_cash_flow",
    ]
    assert len(layer.examples) == 12


def test_the_layer_matches_columns_named_like_its_attributes():
    layer = load_semantic_layer()
    check_layer(layer, _columns(layer))  # does not raise


def test_every_mismatch_with_the_views_is_listed():
    layer = load_semantic_layer()
    columns = _columns(layer)
    del columns["transactions"]["note"]
    columns["transactions"]["shiny_new_column"] = "text"
    del columns["subscriptions"]
    with pytest.raises(SemanticLayerError) as raised:
        check_layer(layer, columns)
    message = str(raised.value)
    assert "transactions.note: not a column" in message
    assert "transactions.shiny_new_column: not described" in message
    assert "subscriptions: no such view in schema agent" in message


def test_only_dimensions_carry_allowed_values():
    layer = load_semantic_layer()
    spend = next(a for a in layer.models[1].attributes if a.attribute == "spend")
    spend.allowed_values = "categories"
    with pytest.raises(SemanticLayerError, match="transactions.spend: only a dimension"):
        check_layer(layer, _columns(layer))


def test_a_typo_in_the_yaml_fails_to_load(tmp_path):
    (tmp_path / "metrics.yaml").write_text("[]")
    (tmp_path / "examples.yaml").write_text("[]")
    (tmp_path / "t.yaml").write_text(
        "model: t\ndescription: d\ngrain: g\nuse_for: []\nnot_for: []\n"
        "attributes:\n  - attribute: a\n    kind: dimension\n    descripton: typo\n"
    )
    with pytest.raises(ValueError, match="descripton"):
        load_semantic_layer(tmp_path)


def test_every_example_step_passes_the_sql_guard():
    for example in load_semantic_layer().examples:
        for sql in example.sql:
            check_query(sql)  # raises RejectedQuery on a bad example


def test_the_version_is_a_stable_short_hash():
    assert layer_version() == layer_version() and len(layer_version()) == 12
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_semantic_layer.py -q`
Expected: FAIL (`No module named 'finance.agent.semantic_layer'`).

- [ ] **Step 3: Write the YAML files**

These are the agent's knowledge of the data. Descriptions are written from the agent's side: what a column means, how to filter it, what it is not. Allowed values only for what the app defines; user data (merchants, notes, bank texts) is explored by the agent. Use block style for `allowed_values`: a meaning with a comma breaks a one-line YAML mapping.

`apps/api/finance/agent/semantic/transactions.yaml`:

```yaml
model: transactions
description: >
  Every money movement of every imported bank account, one row each, with the household's money
  rules already applied: each row says whether it counts as spending, income or a transfer, and
  how much it adds to each total. All accounts belong to one household and all amounts are in
  euros. This is the source for every amount.
grain: >
  One row per movement printed on a bank statement. A transfer between two imported accounts
  appears twice, once leaving and once arriving, both with tx_type = 'transfer'.
use_for:
  - Spending, income and savings for any period, account, category group, category or merchant.
  - What something cost or why money moved, through the user's notes.
  - Listing, counting and ranking movements, such as the largest charges, the most frequent
    merchants or the average ticket.
  - Loans, with the money received, the instalments, the paying account and the total repaid.
  - Comparisons between periods, accounts, categories or merchants.
not_for:
  - Subscription cadence, typical charge or whether a subscription is still active (use
    subscriptions).
  - Account balances, because the balance after each movement is not available.
  - What was bought inside a credit card bill. Card statements are not imported, so each monthly
    settlement is one movement in category credit_card_spending.
attributes:
  - attribute: booked_at
    kind: time
    description: >
      Date the bank booked the movement. Use it for exact date ranges with a half-open interval:
      booked_at >= '2026-07-01' AND booked_at < '2026-08-01'. A card purchase can be booked a day
      or two after it was made.
  - attribute: month
    kind: time
    description: >
      booked_at as 'YYYY-MM' text (for example '2026-07'). Use it to group by month and to filter
      whole months (month = '2026-07', month BETWEEN '2026-01' AND '2026-03'). It sorts
      chronologically as text.
  - attribute: account
    kind: dimension
    description: Name of the bank account as the user sees it in the app.
    allowed_values: accounts
  - attribute: bank
    kind: dimension
    description: Bank that holds the account.
    allowed_values:
      - value: bbva
        meaning: BBVA
      - value: caixabank
        meaning: CaixaBank
  - attribute: amount
    kind: measure
    description: >
      Signed amount as printed on the statement: positive is money in, negative is money out. Use
      it to show single movements and for cash-flow questions (money in and out of an account,
      transfers included). Never SUM it for spending or income, because transfers and refunds
      would distort the total; use spend and income.
  - attribute: direction
    kind: dimension
    description: >
      Whether money came in or went out (the sign of amount). It does not say whether a row is
      spending: a refund comes in and still belongs to spending. Use tx_type for that.
    allowed_values:
      - value: incoming
        meaning: money in (amount > 0)
      - value: outgoing
        meaning: money out (amount < 0)
  - attribute: tx_type
    kind: dimension
    description: What the movement counts as. It follows the category, not the sign.
    allowed_values:
      - value: expense
        meaning: counts in spending, including refunds of purchases (negative spend)
      - value: income
        meaning: counts in income
      - value: transfer
        meaning: >-
          counts in no total (between own accounts, to savings or investments, loan money
          received)
  - attribute: spend
    kind: measure
    description: >
      Money spent: -amount for expense rows, 0 for income and transfer rows. A refund of a
      purchase is negative and lowers spending. SUM(spend) is total spending ("expenses") for any
      filter; transfers are already out.
  - attribute: income
    kind: measure
    description: >
      Money earned: amount for income rows, 0 otherwise. SUM(income) is total income; it never
      includes transfers or loan money received.
  - attribute: category
    kind: dimension
    description: >
      Category of the movement (level 2 of the taxonomy). 'uncategorized' when the movement has no
      category yet; such rows count by their sign until categorized. Different from
      uncategorized_expense, a category for expenses whose purpose is unknown.
    allowed_values: categories
  - attribute: category_group
    kind: dimension
    description: >
      Group of the category (level 1), for broad questions such as "how much on transport".
      'uncategorized' when the movement has no category.
    allowed_values: category_groups
  - attribute: merchant
    kind: dimension
    description: >
      Business name chosen by the app, the same for every branch and spelling of a business (one
      name for "ACME 0042 MADRID" and "ACME FOODS"). NULL when the movement names no business:
      Bizum and transfers to people, cash withdrawals, bank fees, card settlements. A loan is a
      merchant named 'Loan ····' plus the last digits of its contract, unless the user renamed it.
      Names depend on the user's data: find the exact stored name first (SELECT DISTINCT merchant
      ... WHERE merchant ILIKE '%acme%'), then filter with merchant = '<exact name>'.
  - attribute: bank_text
    kind: text
    description: >
      The movement's text from the statement, cleaned: upper case, card numbers and references
      removed. It holds the shop as the bank prints it, the concept typed in a Bizum and the
      reference of a transfer. Search it with ILIKE when merchant is NULL or does not match what
      the user means. Do not group by it, because one business has many spellings.
  - attribute: bank_operation
    kind: dimension
    description: >
      The bank's own label for the kind of operation (card payment, transfer sent, direct debit),
      BBVA only; NULL on CaixaBank accounts. Values depend on the data: look them up with SELECT
      DISTINCT.
  - attribute: note
    kind: text
    description: >
      The user's own note on this movement, written in the app in their own words and any
      language: one word ("móvil") or a phrase ("Rome trip with Ana"). NULL on most rows. It is
      the most reliable account of what was bought or why; the bank text only names the shop.
      When the user asks about an item, a trip, an event or a person, read the distinct notes and
      choose the ones that mean it; do not guess a search word. Show the note when listing
      movements that have one.
  - attribute: is_subscription
    kind: flag
    description: >
      true for a charge of a cancellable recurring service: streaming, software, telecom, gym,
      insurance, memberships. Utilities, rent, mortgage and loans recur but are not
      subscriptions. For the subscription list, cadence and active status, use subscriptions.
  - attribute: needs_review
    kind: flag
    description: >
      true when the app was not confident about the category and the user has not confirmed it.
      Totals include these rows; say so when they are a material part of an answer.
```

`apps/api/finance/agent/semantic/subscriptions.yaml`:

```yaml
model: subscriptions
description: >
  One row per merchant with at least one money-out charge flagged as a subscription, with the
  cadence and active status the app computes from those charges.
grain: One row per subscribed merchant.
use_for:
  - Which subscriptions exist and which are active.
  - What subscriptions cost per month (SUM(monthly_equivalent) over active rows).
  - When a subscription was last charged, and its typical amount.
not_for:
  - Single charges or spending totals (use transactions with is_subscription = true).
  - Subscriptions paid by credit card. Card statements are not imported, so they are not
    itemized.
attributes:
  - attribute: merchant
    kind: dimension
    description: >
      Business name, the same names as transactions.merchant. Names depend on the user's data:
      look them up before filtering.
  - attribute: charges
    kind: measure
    description: Number of charges flagged as a subscription for this merchant.
  - attribute: last_charge
    kind: time
    description: Date of the latest charge.
  - attribute: typical_amount
    kind: measure
    description: The median charge, a positive amount in euros.
  - attribute: cadence
    kind: dimension
    description: How often it charges, from the median gap between charges.
    allowed_values:
      - value: monthly
        meaning: a median gap of 200 days or less, or a single charge so far
      - value: yearly
        meaning: a median gap over 200 days
  - attribute: monthly_equivalent
    kind: measure
    description: >
      The typical amount for a monthly subscription, a twelfth of it for a yearly one. Summed
      over active rows, it is the monthly cost of subscriptions.
  - attribute: active
    kind: flag
    description: >
      true when charged within 45 days (monthly) or 400 days (yearly) of the latest imported
      movement, not of today, so an old import does not make every subscription look cancelled.
```

`apps/api/finance/agent/semantic/metrics.yaml`:

```yaml
# Metric definitions: how the money rules (docs/money-rules.md) add up in SQL. Every entry is
# checked with EXPLAIN as `SELECT <sql> FROM <model>` when the API starts.
- name: expenses
  model: transactions
  description: Total spending, net of refunds. Income and transfer rows add 0.
  sql: SUM(spend)
- name: income
  model: transactions
  description: Total income. It never includes transfers or loan money received.
  sql: SUM(income)
- name: savings
  model: transactions
  description: >
    Income minus expenses. Money moved to the user's own savings or investment accounts counts
    as saved.
  sql: SUM(income) - SUM(spend)
- name: savings_rate
  model: transactions
  description: >
    Share of income saved, computed after summing every account and month of the period; never
    sum or average rates. Empty without income, and it can be negative.
  sql: (SUM(income) - SUM(spend)) / NULLIF(SUM(income), 0)
- name: net_cash_flow
  model: transactions
  description: >
    Money in minus money out of the selected accounts, transfers included: how much they grew or
    shrank. Never a measure of spending.
  sql: SUM(amount)
```

`apps/api/finance/agent/semantic/examples.yaml`:

```yaml
# Query examples, from easy to complex. Each teaches a pattern; merchants and notes are made up.
# Every step must pass the SQL guard and EXPLAIN as agent_reader (checked when the API starts).
- question: How much did I spend in July 2026?
  teaches: Spending is SUM(spend). A whole month filters on month.
  sql:
    - SELECT SUM(spend) AS expenses FROM transactions WHERE month = '2026-07'
- question: Where did my money go in the third quarter of 2026, by group?
  teaches: >
    Rank groups by spending and compute each share with a window function over the grouped sums.
  sql:
    - |
      SELECT category_group, SUM(spend) AS spend,
             ROUND(100 * SUM(spend) / NULLIF(SUM(SUM(spend)) OVER (), 0), 1) AS share_pct
      FROM transactions
      WHERE booked_at >= '2026-07-01' AND booked_at < '2026-10-01' AND tx_type = 'expense'
      GROUP BY category_group
      ORDER BY spend DESC
- question: How much did I save each month this year, and at what rate?
  teaches: >
    Income, expenses, savings and savings rate per month. The rate is computed after summing. Mark
    a month the coverage does not reach to its end as partial in the answer.
  sql:
    - |
      SELECT month, SUM(income) AS income, SUM(spend) AS expenses,
             SUM(income) - SUM(spend) AS savings,
             ROUND(100 * (SUM(income) - SUM(spend)) / NULLIF(SUM(income), 0), 1) AS savings_rate_pct
      FROM transactions
      WHERE booked_at >= '2026-01-01'
      GROUP BY month
      ORDER BY month
- question: How much have I spent at Acme this year?
  teaches: >
    Merchant names are not in the data context: look up the exact name first, then filter on it.
  sql:
    - |
      SELECT merchant, COUNT(*) AS movements
      FROM transactions
      WHERE merchant ILIKE '%acme%'
      GROUP BY merchant
      ORDER BY movements DESC
      LIMIT 20
    - |
      SELECT SUM(spend) AS spend, COUNT(*) AS charges,
             ROUND(SUM(spend) / NULLIF(COUNT(*), 0), 2) AS average_ticket
      FROM transactions
      WHERE merchant = 'Acme Market' AND booked_at >= '2026-01-01' AND tx_type = 'expense'
- question: How much did the trip to Rome cost?
  teaches: >
    Notes are the user's own words. Read the distinct notes first and pick the ones that mean the
    trip, then list those movements with their notes and the total.
  sql:
    - |
      SELECT note, COUNT(*) AS movements, MIN(booked_at) AS first_day, MAX(booked_at) AS last_day,
             SUM(spend) AS spend
      FROM transactions
      WHERE note IS NOT NULL
      GROUP BY note
      ORDER BY last_day DESC
      LIMIT 200
    - |
      SELECT booked_at, merchant, category, spend, note, SUM(spend) OVER () AS total
      FROM transactions
      WHERE note IN ('Rome trip', 'hotel Rome')
      ORDER BY booked_at
- question: How did my spending by group change in August 2026 compared with July?
  teaches: >
    Compute both sides, the absolute change and the % change in SQL. No % on a zero baseline.
  sql:
    - |
      WITH by_month AS (
        SELECT category_group,
               COALESCE(SUM(spend) FILTER (WHERE month = '2026-08'), 0) AS august,
               COALESCE(SUM(spend) FILTER (WHERE month = '2026-07'), 0) AS july
        FROM transactions
        WHERE month IN ('2026-07', '2026-08') AND tx_type = 'expense'
        GROUP BY category_group
      )
      SELECT category_group, august, july, august - july AS change,
             ROUND(100 * (august - july) / NULLIF(july, 0), 1) AS change_pct
      FROM by_month
      ORDER BY change DESC
- question: What do I spend in a normal month?
  teaches: >
    Average complete months only: leave out a month the coverage does not reach to its end.
  sql:
    - |
      SELECT ROUND(AVG(expenses), 2) AS average_monthly_spend, COUNT(*) AS months
      FROM (
        SELECT month, SUM(spend) AS expenses
        FROM transactions
        WHERE month BETWEEN '2026-01' AND '2026-07'
        GROUP BY month
      ) AS monthly
- question: Which restaurants do I spend the most at?
  teaches: >
    Category values come from the data context. Rank merchants inside a category with their
    share.
  sql:
    - |
      SELECT COALESCE(merchant, '(no business named)') AS merchant, COUNT(*) AS visits,
             SUM(spend) AS spend,
             ROUND(100 * SUM(spend) / NULLIF(SUM(SUM(spend)) OVER (), 0), 1) AS share_pct
      FROM transactions
      WHERE category = 'restaurants_bars' AND booked_at >= '2026-01-01'
      GROUP BY 1
      ORDER BY spend DESC
      LIMIT 10
- question: What subscriptions am I paying, and how much a month?
  teaches: >
    Use subscriptions for the list and its cadence. The monthly cost sums monthly_equivalent over
    active rows.
  sql:
    - |
      SELECT merchant, cadence, typical_amount, monthly_equivalent, last_charge,
             SUM(monthly_equivalent) OVER () AS monthly_total
      FROM subscriptions
      WHERE active
      ORDER BY monthly_equivalent DESC
- question: What loans do I have, and how much have I repaid?
  teaches: >
    Money received from a loan is loan_received (a transfer, never income); the instalments are
    loan_payment (spending). Group by the loan's merchant.
  sql:
    - |
      SELECT merchant,
             SUM(amount) FILTER (WHERE category = 'loan_received') AS received,
             COUNT(*) FILTER (WHERE category = 'loan_payment') AS instalments,
             SUM(spend) FILTER (WHERE category = 'loan_payment') AS repaid,
             STRING_AGG(DISTINCT account, ', ') FILTER (WHERE category = 'loan_payment') AS paid_from,
             MAX(booked_at) FILTER (WHERE category = 'loan_payment') AS last_instalment
      FROM transactions
      WHERE category IN ('loan_received', 'loan_payment')
      GROUP BY merchant
      ORDER BY merchant
- question: How much of September 2026's spending is still uncategorized or pending review?
  teaches: >
    Measure how much of a total rests on unconfirmed categories, and say so when it matters.
  sql:
    - |
      SELECT SUM(spend) AS spend,
             COALESCE(SUM(spend) FILTER (WHERE category = 'uncategorized'), 0) AS uncategorized,
             COALESCE(SUM(spend) FILTER (WHERE needs_review), 0) AS pending_review,
             ROUND(100 * COALESCE(SUM(spend) FILTER (
               WHERE category = 'uncategorized' OR needs_review), 0) / NULLIF(SUM(spend), 0), 1)
               AS unconfirmed_pct
      FROM transactions
      WHERE month = '2026-09'
- question: What did I buy at electronics shops this year?
  teaches: >
    When grouping, carry the notes of the grouped rows so you can read what was bought.
  sql:
    - |
      SELECT merchant, COUNT(*) AS purchases, SUM(spend) AS spend,
             STRING_AGG(DISTINCT note, ' | ') AS notes
      FROM transactions
      WHERE category = 'electronics' AND booked_at >= '2026-01-01'
      GROUP BY merchant
      ORDER BY spend DESC
```

- [ ] **Step 4: Write the loader**

Create `apps/api/finance/agent/semantic_layer.py`:

```python
"""The semantic layer: what the agent knows about its views (slice 4 spec, section 5).

Model knowledge and attributes, metric definitions and query examples live in YAML next to this
module, reviewed in pull requests. Column types and app-defined values come from the database.
"""

from hashlib import sha256
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

SEMANTIC_DIR = Path(__file__).parent / "semantic"
_NOT_MODELS = {"metrics", "examples"}

Kind = Literal["measure", "dimension", "time", "text", "flag"]
# Values read from the database when the data context is built (data_context.py).
ValueSource = Literal["accounts", "categories", "category_groups"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a typo in the YAML fails, not silently drops


class AllowedValue(_Strict):
    value: str
    meaning: str


class Attribute(_Strict):
    attribute: str
    kind: Kind
    description: str
    allowed_values: list[AllowedValue] | ValueSource | None = None


class Model(_Strict):
    model: str
    description: str
    grain: str
    use_for: list[str]
    not_for: list[str]
    attributes: list[Attribute]


class Metric(_Strict):
    name: str
    model: str
    description: str
    sql: str


class Example(_Strict):
    question: str
    teaches: str
    sql: list[str]  # one statement per step; lookups come before the final query


class SemanticLayer(_Strict):
    models: list[Model]
    metrics: list[Metric]
    examples: list[Example]


class SemanticLayerError(Exception):
    pass


def load_semantic_layer(directory: Path = SEMANTIC_DIR) -> SemanticLayer:
    def read(path: Path) -> object:
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    models = [read(p) for p in sorted(directory.glob("*.yaml")) if p.stem not in _NOT_MODELS]
    return SemanticLayer(
        models=models,
        metrics=read(directory / "metrics.yaml"),
        examples=read(directory / "examples.yaml"),
    )


def layer_version(directory: Path = SEMANTIC_DIR) -> str:
    """A short hash of the YAML files, recorded on every trace."""
    digest = sha256()
    for path in sorted(directory.glob("*.yaml")):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def check_layer(layer: SemanticLayer, columns: dict[str, dict[str, str]]) -> None:
    """Raise SemanticLayerError listing every mismatch with the live views (view -> column ->
    type). Every column must be described and every description must name a column."""
    problems = []
    for model in layer.models:
        live = columns.get(model.model)
        if live is None:
            problems.append(f"{model.model}: no such view in schema agent")
            continue
        described = [a.attribute for a in model.attributes]
        problems += [f"{model.model}.{c}: not a column" for c in described if c not in live]
        problems += [f"{model.model}.{c}: not described" for c in live if c not in described]
        problems += [
            f"{model.model}.{a.attribute}: only a dimension has allowed values"
            for a in model.attributes
            if a.allowed_values is not None and a.kind != "dimension"
        ]
    names = {model.model for model in layer.models}
    problems += [
        f"metric {m.name}: unknown model {m.model}" for m in layer.metrics if m.model not in names
    ]
    if problems:
        raise SemanticLayerError(
            "the semantic layer does not match the views:\n- " + "\n- ".join(problems)
        )
```

The hatch wheel build includes the YAML files because they live inside the `finance` package.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_semantic_layer.py -q`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/agent/semantic apps/api/finance/agent/semantic_layer.py apps/api/tests/test_semantic_layer.py
git commit -m "feat: semantic layer for the chat agent"
```

---

### Task 6: Catalog, startup validation and the data context

**Files:**
- Create: `apps/api/finance/agent/catalog.py`, `apps/api/finance/agent/data_context.py`
- Test: `apps/api/tests/test_data_context.py` (unit), `apps/api/tests/test_catalog_db.py` (integration)

**Interfaces:**
- Consumes: Task 4 (`explain`), Task 3 (`check_query`), Task 5 (layer, `check_layer`).
- Produces:
  - `catalog.Category(slug, level1, tx_type, what, not_for)`, `Account(name, bank, data_from, data_to)`, `Catalog(categories, accounts, latest_day)` (frozen dataclasses).
  - `read_columns(conn) -> dict[str, dict[str, str]]` (view → column → data type), `read_catalog(pool) -> Catalog`, `validate_layer(pool, layer) -> dict[str, dict[str, str]]` (raises `SemanticLayerError` listing every mismatch, guard rejection or `EXPLAIN` error).
  - `data_context.render_data_context(layer, columns, catalog, today: date) -> str`.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_data_context.py`:

```python
from datetime import date

from finance.agent.catalog import Account, Catalog, Category
from finance.agent.data_context import render_data_context
from finance.agent.semantic_layer import (
    AllowedValue,
    Attribute,
    Example,
    Metric,
    Model,
    SemanticLayer,
    load_semantic_layer,
)

CATALOG = Catalog(
    categories=[
        Category("groceries", "shopping", "expense", "supermarkets, bakeries", None),
        Category("rent", "home", "expense", "monthly rent", "mortgage instalments"),
    ],
    accounts=[
        Account("BBVA ····0001", "bbva", date(2025, 1, 1), date(2025, 12, 31)),
        Account("Joe's savings", "caixabank", None, None),
    ],
    latest_day=date(2025, 12, 31),
)

TINY = SemanticLayer(
    models=[
        Model(
            model="transactions",
            description="Every movement.\n",
            grain="One row per movement.",
            use_for=["Spending."],
            not_for=["Balances."],
            attributes=[
                Attribute(attribute="spend", kind="measure", description="Money spent."),
                Attribute(
                    attribute="direction",
                    kind="dimension",
                    description="In or out.",
                    allowed_values=[AllowedValue(value="incoming", meaning="money in")],
                ),
                Attribute(
                    attribute="category",
                    kind="dimension",
                    description="Category.",
                    allowed_values="categories",
                ),
                Attribute(
                    attribute="category_group",
                    kind="dimension",
                    description="Group.",
                    allowed_values="category_groups",
                ),
                Attribute(
                    attribute="account",
                    kind="dimension",
                    description="Account.",
                    allowed_values="accounts",
                ),
            ],
        )
    ],
    metrics=[Metric(name="expenses", model="transactions", description="Total.", sql="SUM(spend)")],
    examples=[Example(question="July?", teaches="SUM(spend).", sql=["SELECT 1", "SELECT 2"])],
)
COLUMNS = {
    "transactions": {
        "spend": "numeric",
        "direction": "text",
        "category": "text",
        "category_group": "text",
        "account": "text",
    }
}

EXPECTED = """\
# Data context

## Data model

### transactions
Description: Every movement.
Grain: One row per movement.
Use for:
- Spending.
Not for:
- Balances.
Columns:
- spend (numeric, measure): Money spent.
- direction (text, dimension): In or out.
  Allowed values:
  - incoming: money in
- category (text, dimension): Category.
  Allowed values:
  - groceries (group shopping, expense): supermarkets, bakeries
  - rent (group home, expense): monthly rent. Not for: mortgage instalments
  - uncategorized: no category yet; the movement counts by its sign
- category_group (text, dimension): Group.
  Allowed values:
  - shopping (expense): groceries
  - home (expense): rent
  - uncategorized: movements with no category yet
- account (text, dimension): Account.
  Allowed values:
  - 'BBVA ····0001' (bbva): statements from 2025-01-01 to 2025-12-31
  - 'Joe''s savings' (caixabank): no statements imported

## Metrics
- expenses = SUM(spend) on transactions: Total.

## Query examples

1. July?
   Teaches: SUM(spend).
   Step 1:
   SELECT 1
   Step 2:
   SELECT 2

## Now
Today: 2026-01-05 (Monday)
Latest imported movement: 2025-12-31
"""


def test_the_rendered_context_is_exactly_this_text():
    assert render_data_context(TINY, COLUMNS, CATALOG, date(2026, 1, 5)) == EXPECTED


def test_the_real_layer_renders_every_attribute_with_its_type_within_budget():
    layer = load_semantic_layer()
    columns = {m.model: {a.attribute: "text" for a in m.attributes} for m in layer.models}
    text = render_data_context(layer, columns, CATALOG, date(2026, 1, 5))
    for model in layer.models:
        for a in model.attributes:
            assert f"- {a.attribute} (text, {a.kind}): " in text
    assert len(text) < 32_000  # about 8,000 tokens: the spec budgets 4,500 for a real taxonomy


def test_an_empty_ledger_says_nothing_is_imported_yet():
    empty = Catalog(categories=CATALOG.categories, accounts=[], latest_day=None)
    text = render_data_context(TINY, COLUMNS, empty, date(2026, 1, 5))
    assert "Latest imported movement: nothing imported yet" in text
```

Create `apps/api/tests/test_catalog_db.py`:

```python
import asyncio

import pytest

from finance.agent.catalog import read_catalog, validate_layer
from finance.agent.semantic_layer import load_semantic_layer
from finance.db import async_pool

pytestmark = pytest.mark.integration


def test_the_semantic_layer_matches_the_views_and_all_its_sql_compiles():
    async def go():
        async with async_pool() as pool:
            return await validate_layer(pool, load_semantic_layer())

    columns = asyncio.run(go())
    assert columns["transactions"]["booked_at"] == "date"
    assert columns["subscriptions"]["active"] == "boolean"


def test_the_catalog_reads_the_taxonomy_in_seed_order_and_every_account():
    async def go():
        async with async_pool() as pool:
            return await read_catalog(pool)

    catalog = asyncio.run(go())
    assert len(catalog.categories) >= 57
    assert catalog.categories[0].slug == "rent"  # the first slug of supabase/seed/categories.yaml
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_data_context.py -q`
Expected: FAIL (`No module named 'finance.agent.catalog'`).

- [ ] **Step 3: Implement**

Create `apps/api/finance/agent/catalog.py`:

```python
"""What the database tells the agent: column types, the app-defined values (taxonomy, accounts
with their statement coverage) and the latest imported day. Also proves at startup that the
semantic layer matches the views and that every metric and example compiles."""

from dataclasses import dataclass
from datetime import date

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from finance.agent.semantic_layer import SemanticLayer, SemanticLayerError, check_layer
from finance.agent.sql_guard import RejectedQuery, check_query
from finance.agent.sql_runner import explain


@dataclass(frozen=True)
class Category:
    slug: str
    level1: str
    tx_type: str
    what: str
    not_for: str | None


@dataclass(frozen=True)
class Account:
    name: str
    bank: str
    data_from: date | None
    data_to: date | None


@dataclass(frozen=True)
class Catalog:
    categories: list[Category]
    accounts: list[Account]
    latest_day: date | None


async def read_columns(conn: AsyncConnection) -> dict[str, dict[str, str]]:
    rows = await (
        await conn.execute(
            "select table_name, column_name, data_type from information_schema.columns"
            " where table_schema = 'agent' order by table_name, ordinal_position"
        )
    ).fetchall()
    columns: dict[str, dict[str, str]] = {}
    for row in rows:
        columns.setdefault(row["table_name"], {})[row["column_name"]] = row["data_type"]
    return columns


async def read_catalog(pool: AsyncConnectionPool) -> Catalog:
    async with pool.connection() as conn:
        categories = await (
            await conn.execute(
                "select slug, level1, tx_type, what, not_for from categories order by position"
            )
        ).fetchall()
        accounts = await (
            await conn.execute(
                "select a.name, a.bank::text as bank, min(i.period_start) as data_from,"
                " max(i.period_end) as data_to"
                " from accounts a left join imports i on i.account_id = a.id"
                " group by a.id, a.name, a.bank order by a.name"
            )
        ).fetchall()
        latest = await (
            await conn.execute("select max(booked_at) as day from transactions")
        ).fetchone()
    return Catalog(
        categories=[Category(**row) for row in categories],
        accounts=[Account(**row) for row in accounts],
        latest_day=latest["day"],
    )


async def validate_layer(
    pool: AsyncConnectionPool, layer: SemanticLayer
) -> dict[str, dict[str, str]]:
    """Return the view columns and their types, or raise SemanticLayerError."""
    async with pool.connection() as conn:
        columns = await read_columns(conn)
    check_layer(layer, columns)
    statements = [(f"metric {m.name}", f"SELECT {m.sql} FROM {m.model}") for m in layer.metrics]
    statements += [
        (f"example {n} step {s}", sql)
        for n, example in enumerate(layer.examples, start=1)
        for s, sql in enumerate(example.sql, start=1)
    ]
    problems = []
    for label, sql in statements:
        try:
            check_query(sql)
        except RejectedQuery as rejected:
            problems.append(f"{label}: {rejected.reason}")
            continue
        if error := await explain(pool, sql):
            problems.append(f"{label}: {error}")
    if problems:
        raise SemanticLayerError("semantic layer SQL does not compile:\n- " + "\n- ".join(problems))
    return columns
```

Create `apps/api/finance/agent/data_context.py`:

```python
"""Render the data context the agent receives every turn, next to its instructions: the data
model with app-defined values, the metric definitions, the query examples, and today's date."""

from datetime import date
from textwrap import indent

from finance.agent.catalog import Account, Catalog, Category
from finance.agent.semantic_layer import Attribute, SemanticLayer

UNCATEGORIZED = "uncategorized"


def _sql_literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _category(c: Category) -> str:
    line = f"- {c.slug} (group {c.level1}, {c.tx_type}): {c.what}"
    return f"{line}. Not for: {c.not_for}" if c.not_for else line


def _groups(categories: list[Category]) -> list[str]:
    groups: dict[tuple[str, str], list[str]] = {}
    for c in categories:
        groups.setdefault((c.level1, c.tx_type), []).append(c.slug)
    return [
        f"- {level1} ({tx_type}): {', '.join(slugs)}" for (level1, tx_type), slugs in groups.items()
    ]


def _account(a: Account) -> str:
    if a.data_from is None:
        return f"- {_sql_literal(a.name)} ({a.bank}): no statements imported"
    return f"- {_sql_literal(a.name)} ({a.bank}): statements from {a.data_from} to {a.data_to}"


def _values(attribute: Attribute, catalog: Catalog) -> list[str]:
    source = attribute.allowed_values
    if source is None:
        return []
    if source == "categories":
        lines = [_category(c) for c in catalog.categories]
        return [*lines, f"- {UNCATEGORIZED}: no category yet; the movement counts by its sign"]
    if source == "category_groups":
        return [*_groups(catalog.categories), f"- {UNCATEGORIZED}: movements with no category yet"]
    if source == "accounts":
        return [_account(a) for a in catalog.accounts]
    return [f"- {v.value}: {v.meaning.strip()}" for v in source]


def render_data_context(
    layer: SemanticLayer, columns: dict[str, dict[str, str]], catalog: Catalog, today: date
) -> str:
    lines = ["# Data context", "", "## Data model"]
    for model in layer.models:
        lines += ["", f"### {model.model}", f"Description: {model.description.strip()}"]
        lines += [f"Grain: {model.grain.strip()}", "Use for:"]
        lines += [f"- {item.strip()}" for item in model.use_for]
        lines += ["Not for:"] + [f"- {item.strip()}" for item in model.not_for]
        lines.append("Columns:")
        for a in model.attributes:
            data_type = columns[model.model][a.attribute]
            lines.append(f"- {a.attribute} ({data_type}, {a.kind}): {a.description.strip()}")
            if values := _values(a, catalog):
                lines += ["  Allowed values:"] + [f"  {v}" for v in values]
    lines += ["", "## Metrics"]
    lines += [f"- {m.name} = {m.sql} on {m.model}: {m.description.strip()}" for m in layer.metrics]
    lines += ["", "## Query examples"]
    for number, example in enumerate(layer.examples, start=1):
        lines += ["", f"{number}. {example.question}", f"   Teaches: {example.teaches.strip()}"]
        for step, sql in enumerate(example.sql, start=1):
            label = "SQL" if len(example.sql) == 1 else f"Step {step}"
            lines += [f"   {label}:", indent(sql.strip(), "   ")]
    latest = catalog.latest_day.isoformat() if catalog.latest_day else "nothing imported yet"
    lines += ["", "## Now", f"Today: {today.isoformat()} ({today:%A})"]
    lines.append(f"Latest imported movement: {latest}")
    return "\n".join(lines) + "\n"
```

Account names are rendered as SQL literals (a quote doubled), because the agent copies them into `WHERE account = ...`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_data_context.py -q && uv run pytest tests/test_catalog_db.py -q -m integration`
Expected: 3 passed, then 2 passed. The second proves every metric and every example step compiles as `agent_reader` against the real views.

- [ ] **Step 5: Look at the real context once**

Run:

```bash
uv run python -c "
import asyncio
from datetime import date
from finance.agent.catalog import read_catalog, validate_layer
from finance.agent.data_context import render_data_context
from finance.agent.semantic_layer import load_semantic_layer
from finance.db import async_pool
async def go():
    async with async_pool() as pool:
        layer = load_semantic_layer()
        return render_data_context(layer, await validate_layer(pool, layer), await read_catalog(pool), date.today())
text = asyncio.run(go())
print(len(text), 'characters')
"
```

Expected: about 24,000 characters (about 6,000 tokens). Do not paste the output anywhere: it lists real account names.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/agent/catalog.py apps/api/finance/agent/data_context.py apps/api/tests/test_data_context.py apps/api/tests/test_catalog_db.py
git commit -m "feat: data context with app-defined values and coverage"
```

---

### Task 7: Instructions and the `run_sql` tool

**Files:**
- Create: `apps/api/finance/agent/prompts/system.md`, `apps/api/finance/agent/prompts/summary.md`, `apps/api/finance/agent/prompt.py`, `apps/api/finance/agent/tools.py`
- Test: `apps/api/tests/test_run_sql_tool.py`

**Interfaces:**
- Consumes: `QueryResult` (Task 4).
- Produces: `prompt.INSTRUCTIONS`, `SUMMARY_PROMPT` (contains `{messages}`), `PROMPT_VERSION` (12 hex chars), `system_message(data_context) -> SystemMessage` (two text blocks: instructions, data context); `tools.RunQuery = Callable[[str], Awaitable[QueryResult]]`, `format_for_model(result, rows_shown, max_chars) -> str`, `make_run_sql(run_query, rows_shown, max_chars) -> BaseTool` (name `run_sql`, one argument `sql`, `response_format="content_and_artifact"`, artifact = `QueryResult.model_dump()`).

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_run_sql_tool.py`:

```python
import asyncio

from finance.agent.models import QueryResult
from finance.agent.tools import format_for_model, make_run_sql

ROWS = QueryResult(
    sql="SELECT month, spend FROM t",
    columns=["month", "spend"],
    rows=[["2026-07", "120.50"], ["2026-08", None]],
    row_count=2,
)


def test_rows_read_as_a_compact_table():
    assert format_for_model(ROWS, rows_shown=50, max_chars=8000) == (
        "rows: 2\nmonth | spend\n2026-07 | 120.50\n2026-08 | "
    )


def test_a_cut_result_says_how_to_narrow_it():
    many = QueryResult(
        sql="s", columns=["n"], rows=[[str(n)] for n in range(5)], row_count=5, truncated=True
    )
    text = format_for_model(many, rows_shown=2, max_chars=8000)
    assert text.splitlines()[0] == "rows: more than 5"
    assert text.splitlines()[-1] == (
        "(showing 2 of more than 5 rows: aggregate, filter or add ORDER BY ... LIMIT)"
    )


def test_the_character_cap_cuts_rows_too():
    wide = QueryResult(sql="s", columns=["t"], rows=[["x" * 100]] * 10, row_count=10)
    text = format_for_model(wide, rows_shown=50, max_chars=350)
    assert len(text) < 450 and "(showing 3 of 10 rows" in text  # header + 3 rows of 101 fit in 350


def test_errors_and_empty_results_are_short():
    error = QueryResult(sql="s", error='column "x" does not exist', hint="Use the listed columns.")
    assert format_for_model(error, 50, 8000) == (
        'error: column "x" does not exist\nhint: Use the listed columns.'
    )
    assert format_for_model(QueryResult(sql="s"), 50, 8000) == "rows: 0 (nothing matched)"


def test_the_tool_returns_the_text_for_the_model_and_the_whole_result_as_artifact():
    async def run_query(sql):
        return ROWS

    tool = make_run_sql(run_query, rows_shown=50, max_chars=8000)
    message = asyncio.run(
        tool.ainvoke({"type": "tool_call", "name": "run_sql", "args": {"sql": "x"}, "id": "c1"})
    )
    assert message.content.startswith("rows: 2")
    assert message.artifact == ROWS.model_dump()
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_run_sql_tool.py -q`
Expected: FAIL (`No module named 'finance.agent.tools'`).

- [ ] **Step 3: Write the prompts**

`apps/api/finance/agent/prompts/system.md` (spec Appendix A; it names no table or column):

```markdown
# Role
You are the analyst of the user's household finances. You answer questions about the user's own
bank movements by querying them with `run_sql`. Accuracy over fluency. Explicit assumptions over
hidden ones.

In scope: anything the data can answer: spending, income, savings, merchants, categories, the
user's notes, subscriptions, loans, comparisons and trends.
Out of scope: everything else, including financial advice, general knowledge and changing data.
- Greetings or thanks: reply in one line and say what you can do.
- Out of scope: say so in one sentence and offer two or three questions you can answer.
- Requests to change data (categories, notes): you cannot; point to the Review or Transactions page.

# Rule priority (when two rules conflict, the higher one wins)
1. Data integrity: only the tables, columns and values in the data context.
2. Money rules: the definitions in the data context.
3. Numeric correctness.
4. Clarity.
5. Style.

# Invariants
- Every number you state comes from a `run_sql` result in this turn. Numbers from earlier turns
  are queried again; their results may have been cleared from your context.
- Spending uses `spend`, income uses `income`. `amount` is only for single movements and cash flow.
- Ratios and rates are computed after summing, never summed or averaged.
- A filter value must be an allowed value or the result of a lookup query. Never a guess.
- When a filter finds nothing, never widen the scope silently.

# Workflow (every data question)
1. Understand: metric, period, filters, grain, and output shape (single number, breakdown,
   ranking, list, comparison, trend).
2. Resolve the period (see Dates).
3. Resolve every filter value:
   - Column with allowed values: map the user's words to stored values through their meanings.
   - Column without allowed values: run a separate lookup first
     (SELECT DISTINCT <column>, COUNT(*) ... WHERE <column> ILIKE '%term%' ... LIMIT 20), try
     variants (accents, short brand name, singular), then filter with the exact values found.
     Never look up and aggregate in the same query.
   - Notes: the user's words rarely match literally. List the distinct notes (with counts and
     dates) and choose by meaning.
   Lookups for different filters can run in parallel; the final query runs after them.
4. Write one query that answers the question. Totals, shares, averages and deltas are computed in
   SQL, never in your head. When listing movements, include the note.
5. Check before running: every column exists in that model, every filter is resolved, measures
   are aggregated and never grouped, the period is explicit, listings have a LIMIT.
6. On an error, read the message and its hint and fix it with a different approach. After two
   failed attempts at the same query, stop: say what you could not do and offer a related
   question you can answer. Never resend a query that failed.
7. Answer (see Answer format).

# Clarifying
Ask one short question with concrete options only when the ambiguity survives the allowed values
and the lookups, and the readings would give materially different answers. Otherwise take the
dominant reading and state it in "How I counted it".

# Dates
- Today and the data coverage of each account are in the data context.
- Relative periods resolve against today: "last week" is the previous Monday to Sunday, "last
  month" the previous calendar month, "this year" 1 January to today.
- A month or season without a year is the latest one that has started; state the year.
- A period after the end of the coverage: say where the data ends; answer the covered part marked
  as partial, or offer the latest equivalent period with data.
- A month without data is "no data", never zero. Monthly averages use complete months only.

# Comparisons
- Both sides share the metric, filters and period length; only the compared axis changes.
- Show both values, the absolute change and the % change, all computed in SQL, even if the user
  did not ask for the change. With a zero or empty baseline, give no % and say why.
- "Compared with before" means the previous period of the same length. When the current period
  is partial, cut the previous one after the same number of days.

# No data
Before saying nothing matches, check: the lookup was case-insensitive and tried variants and
accents; the value exists; the period is inside the coverage; the filters do not contradict each
other. Then say plainly what you searched and offer a next step.

# Answer format
- Reply in the language of the user's latest message.
- First the answer: one or two sentences with the key number.
- Then only the detail that helps: a short list, or a Markdown table when the data is truly
  tabular (at most 12 rows; say how many more there are).
- End with "How I counted it": at most three short bullets in plain words: exact dates,
  accounts, and what is in or out (transfers excluded, refunds subtract, the share pending
  review when it matters).
- Money with two decimals in the reader's format (1.234,56 € or €1,234.56). Spending reads as a
  positive amount.
- Never mention tables, columns, SQL or tools, and do not narrate your steps: the app shows the
  queries separately.
- You cannot draw charts or produce files.

# Reading the data context
- The data model is the only source of tables and columns. Each column has a kind:
  measure (aggregate it, never group by it), dimension (group or filter; with allowed values use
  them as they are, without them look up first), time (filter and group periods), text (search it,
  read it, never group by it), flag (true or false filter).
- Metrics: use their definitions exactly.
- Query examples: patterns to adapt, not templates to copy.
```

`apps/api/finance/agent/prompts/summary.md` (replaces LangChain's default summary prompt, which is written for coding agents):

```markdown
You are compacting a conversation between a user and the analyst of their household finances.
The summary replaces the older messages, so keep everything the analyst needs to continue:

- The user's questions, in order, and what each was about.
- Periods, accounts, categories and filters used, with exact dates.
- Values already resolved: exact merchant names, notes and categories the user meant.
- Figures already given, each with its period and filters. They are context only: any number
  stated again must be queried again.
- Definitions or preferences the user stated (for example "count Bizum to my partner as
  restaurants").
- Questions still open.

Write short factual bullets in English. Do not add advice or new conclusions.

<messages>
{messages}
</messages>
```

- [ ] **Step 4: Implement**

Create `apps/api/finance/agent/prompt.py`:

```python
"""The agent's instructions and the system message built on every model call (spec section 7.1).

The instructions name no table or column: the data model arrives as the data context, so a change
to the views never touches this text, and a prompt change never breaks a stored thread.
"""

from hashlib import sha256
from pathlib import Path

from langchain_core.messages import SystemMessage

PROMPTS_DIR = Path(__file__).parent / "prompts"
INSTRUCTIONS = (PROMPTS_DIR / "system.md").read_text(encoding="utf-8")
SUMMARY_PROMPT = (PROMPTS_DIR / "summary.md").read_text(encoding="utf-8")
PROMPT_VERSION = sha256(INSTRUCTIONS.encode()).hexdigest()[:12]


def system_message(data_context: str) -> SystemMessage:
    """Instructions first (identical every turn, so the provider caches them), data context next."""
    return SystemMessage(
        content=[{"type": "text", "text": INSTRUCTIONS}, {"type": "text", "text": data_context}]
    )
```

Create `apps/api/finance/agent/tools.py`:

```python
"""`run_sql`, the agent's only tool: a compact table for the model, the full result as artifact."""

from collections.abc import Awaitable, Callable

from langchain.tools import tool
from langchain_core.tools import BaseTool

from finance.agent.models import QueryResult

RunQuery = Callable[[str], Awaitable[QueryResult]]


def format_for_model(result: QueryResult, rows_shown: int, max_chars: int) -> str:
    """The row count, a header and `|`-separated rows; cut by rows and characters, and said so."""
    if result.error:
        return f"error: {result.error}" + (f"\nhint: {result.hint}" if result.hint else "")
    if result.row_count == 0:
        return "rows: 0 (nothing matched)"
    total = f"more than {result.row_count}" if result.truncated else str(result.row_count)
    lines = [f"rows: {total}", " | ".join(result.columns)]
    size = sum(len(line) + 1 for line in lines)
    for row in result.rows[:rows_shown]:
        line = " | ".join("" if value is None else value for value in row)
        if size + len(line) + 1 > max_chars:
            break
        lines.append(line)
        size += len(line) + 1
    shown = len(lines) - 2
    if shown < result.row_count or result.truncated:
        lines.append(
            f"(showing {shown} of {total} rows: aggregate, filter or add ORDER BY ... LIMIT)"
        )
    return "\n".join(lines)


def make_run_sql(run_query: RunQuery, rows_shown: int, max_chars: int) -> BaseTool:
    @tool("run_sql", response_format="content_and_artifact", parse_docstring=True)
    async def run_sql(sql: str) -> tuple[str, dict]:
        """Run one read-only PostgreSQL SELECT over the views transactions and subscriptions.

        Use it for lookups (SELECT DISTINCT ... ILIKE ... LIMIT) and for the final query.
        Returns the row count and the rows as a compact table.

        Args:
            sql: One SELECT statement. No other statement runs.
        """
        result = await run_query(sql)
        return format_for_model(result, rows_shown, max_chars), result.model_dump()

    return run_sql
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_run_sql_tool.py -q`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/agent/prompts apps/api/finance/agent/prompt.py apps/api/finance/agent/tools.py apps/api/tests/test_run_sql_tool.py
git commit -m "feat: chat instructions and the run_sql tool"
```

---

### Task 8: Middleware and the agent graph

**Files:**
- Create: `apps/api/finance/agent/middleware.py`, `apps/api/finance/agent/graph.py`
- Modify: `apps/api/tests/fakes.py`
- Test: `apps/api/tests/test_agent_graph.py`

**Interfaces:**
- Consumes: Task 1 (`ChatSettings`), Task 7 (`SUMMARY_PROMPT`, `system_message`, `make_run_sql`).
- Produces:
  - `middleware.INFRA_MESSAGE`, `CANCELLED`, `CLEARED`, `NOTICE_NODES` (nodes whose AI messages reach the user: `ModelCallLimitMiddleware.before_model`, `stop_on_infra_error.before_model`), `close_dangling_tool_calls`, `stop_on_infra_error`, `system_prompt`, `build_middleware(chat, summary_model) -> list`.
  - `graph.AgentContext(data_context: str)`, `ChatModels(agent, summary, title)`, `chat_models(chat) -> ChatModels`, `build_agent(models, tools, chat, checkpointer)`.
  - `tests/fakes.py`: `ScriptedChatModel(responses=[...])` (records `calls`), `tool_call(sql, call_id) -> AIMessage`.

- [ ] **Step 1: Add the scripted chat model to `tests/fakes.py`**

Replace the module docstring and imports at the top with:

```python
"""Scripted jev and chat models for unit tests: no network, deterministic answers."""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from finance.categorization.jev_client import JevAnswer, JevResult
```

Append:

```python
class ScriptedChatModel(BaseChatModel):
    """A chat model that answers from a script and records every request. create_agent binds
    tools to it; the script decides which tool calls it makes."""

    responses: list[BaseMessage]
    calls: list[list[BaseMessage]] = Field(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.calls.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self.responses.pop(0))])

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs) -> "ScriptedChatModel":
        return self


def tool_call(sql: str, call_id: str) -> AIMessage:
    """A scripted model turn that calls run_sql once."""
    return AIMessage(
        content="", tool_calls=[{"name": "run_sql", "args": {"sql": sql}, "id": call_id}]
    )
```

LangChain's own `GenericFakeChatModel` cannot be used: it streams nothing for a message that only carries tool calls (`No generations found in stream`).

- [ ] **Step 2: Write the failing tests**

Create `apps/api/tests/test_agent_graph.py`:

```python
import asyncio

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from finance.agent.graph import AgentContext, ChatModels, build_agent
from finance.agent.middleware import CANCELLED, CLEARED, INFRA_MESSAGE
from finance.agent.models import QueryResult
from finance.agent.prompt import INSTRUCTIONS
from finance.agent.tools import make_run_sql
from finance.settings import ChatSettings
from tests.fakes import ScriptedChatModel, tool_call

CONFIG = {"configurable": {"thread_id": "t1"}}
CONTEXT = AgentContext(data_context="DATA CONTEXT")


def _agent(model, run_query=None, **chat):
    async def ok(sql):
        return QueryResult(sql=sql, columns=["n"], rows=[["1"]], row_count=1)

    tool = make_run_sql(run_query or ok, rows_shown=50, max_chars=8000)
    models = ChatModels(agent=model, summary=model, title=model)
    return build_agent(models, [tool], ChatSettings(**chat), InMemorySaver())


def _ask(agent, text, config=CONFIG):
    return asyncio.run(agent.ainvoke({"messages": [HumanMessage(text)]}, config, context=CONTEXT))


def test_one_query_then_an_answer_with_instructions_and_data_context_as_system_blocks():
    model = ScriptedChatModel(responses=[tool_call("SELECT 1", "c1"), AIMessage("One.")])
    agent = _agent(model)
    result = _ask(agent, "how many?")
    system = model.calls[0][0]
    assert isinstance(system, SystemMessage)
    assert [block["text"] for block in system.content] == [INSTRUCTIONS, "DATA CONTEXT"]
    types = [type(m).__name__ for m in result["messages"]]
    assert types == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]
    assert result["messages"][2].content == "rows: 1\nn\n1"
    assert result["messages"][-1].content == "One."


def test_a_tool_call_left_unanswered_is_closed_before_the_next_turn():
    model = ScriptedChatModel(responses=[AIMessage("Fine.")])
    agent = _agent(model)
    dangling = [HumanMessage("q1"), tool_call("SELECT 1", "c1")]
    asyncio.run(agent.aupdate_state(CONFIG, {"messages": dangling}))
    _ask(agent, "q2")
    seen = model.calls[0][1:]  # after the system message
    assert [type(m).__name__ for m in seen] == [
        "HumanMessage",
        "AIMessage",
        "ToolMessage",
        "HumanMessage",
    ]
    assert seen[2].content == CANCELLED and seen[2].tool_call_id == "c1"


def test_an_unreachable_database_ends_the_turn_without_another_model_call():
    async def down(sql):
        return QueryResult(sql=sql, error="connection refused", infra_error=True)

    model = ScriptedChatModel(responses=[tool_call("SELECT 1", "c1"), AIMessage("never")])
    result = _ask(_agent(model, down), "q")
    assert len(model.calls) == 1
    assert result["messages"][-1].content == INFRA_MESSAGE


def test_after_the_query_limit_the_model_answers_with_what_it_has():
    calls = [tool_call(f"SELECT {n}", f"c{n}") for n in range(3)]
    model = ScriptedChatModel(responses=[*calls, AIMessage("Done.")])
    result = _ask(_agent(model, max_sql_calls_per_turn=2), "q")
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert "Do not call 'run_sql' again" in tool_messages[-1].content
    assert result["messages"][-1].content == "Done."


def test_old_query_results_leave_the_request_but_keep_their_sql():
    async def wide(sql):
        return QueryResult(sql=sql, columns=["t"], rows=[["x" * 3000]], row_count=1)

    calls = [tool_call(f"SELECT {n}", f"c{n}") for n in range(3)]
    model = ScriptedChatModel(responses=[*calls, AIMessage("Done.")])
    agent = _agent(model, wide, clear_tool_results_trigger_tokens=1000, clear_tool_results_keep=1)
    _ask(agent, "q")
    last_request = model.calls[-1]
    results = [m.content for m in last_request if isinstance(m, ToolMessage)]
    assert results[0] == CLEARED and results[-1].startswith("rows: 1")
    assert last_request[2].tool_calls[0]["args"]["sql"] == "SELECT 0"


def test_the_system_message_is_never_stored_in_the_thread():
    model = ScriptedChatModel(responses=[AIMessage("Hi.")])
    agent = _agent(model)
    _ask(agent, "hello")
    state = asyncio.run(agent.aget_state(CONFIG))
    assert not any(isinstance(m, SystemMessage) for m in state.values["messages"])
```

- [ ] **Step 3: Run them to see them fail**

Run: `uv run pytest tests/test_agent_graph.py -q`
Expected: FAIL (`No module named 'finance.agent.graph'`).

- [ ] **Step 4: Implement**

Create `apps/api/finance/agent/middleware.py`:

```python
"""The agent's middleware stack (spec section 7.3): built-in limits and context management, plus
three small hooks of our own."""

from typing import Any

from langchain.agents.middleware import (
    AgentState,
    ClearToolUsesEdit,
    ContextEditingMiddleware,
    ModelCallLimitMiddleware,
    ModelRequest,
    SummarizationMiddleware,
    ToolCallLimitMiddleware,
    before_agent,
    before_model,
    dynamic_prompt,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, RemoveMessage, SystemMessage, ToolMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

from finance.agent.prompt import SUMMARY_PROMPT, system_message
from finance.settings import ChatSettings

INFRA_MESSAGE = "I can't reach your database right now. Try again in a moment."
CANCELLED = "Cancelled: the user stopped the answer before this query returned."
CLEARED = "[result cleared: run the query again if you need these numbers]"
# Middleware nodes whose AI messages the user must see (stream adapter).
NOTICE_NODES = frozenset(
    {"ModelCallLimitMiddleware.before_model", "stop_on_infra_error.before_model"}
)


@before_agent(name="close_dangling_tool_calls")
def close_dangling_tool_calls(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """A stopped turn can leave a tool call without its result, and model providers reject such
    a history. Answer each one with a cancellation right after its call (the idea of deepagents'
    PatchToolCallsMiddleware, not worth that dependency)."""
    messages = state["messages"]
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    patched, changed = [], False
    for message in messages:
        patched.append(message)
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                if call["id"] not in answered:
                    patched.append(
                        ToolMessage(CANCELLED, tool_call_id=call["id"], name=call["name"])
                    )
                    changed = True
    if not changed:
        return None
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *patched]}


@before_model(can_jump_to=["end"], name="stop_on_infra_error")
def stop_on_infra_error(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """When the database is unreachable, end the turn with a fixed message: another model call
    would not heal it (agents.mdc: fail loud on infrastructure failures)."""
    for message in reversed(state["messages"]):
        if not isinstance(message, ToolMessage):
            break
        if isinstance(message.artifact, dict) and message.artifact.get("infra_error"):
            return {"messages": [AIMessage(INFRA_MESSAGE)], "jump_to": "end"}
    return None


@dynamic_prompt
def system_prompt(request: ModelRequest) -> SystemMessage:
    return system_message(request.runtime.context.data_context)


def build_middleware(chat: ChatSettings, summary_model: BaseChatModel) -> list:
    return [
        close_dangling_tool_calls,
        SummarizationMiddleware(
            model=summary_model,
            trigger=("tokens", chat.summary_trigger_tokens),
            keep=("messages", chat.summary_keep_messages),
            summary_prompt=SUMMARY_PROMPT,
            trim_tokens_to_summarize=None,  # the default 4,000 could drop the previous summary
        ),
        ContextEditingMiddleware(
            edits=[
                ClearToolUsesEdit(
                    trigger=chat.clear_tool_results_trigger_tokens,
                    keep=chat.clear_tool_results_keep,
                    placeholder=CLEARED,
                )
            ]
        ),
        ToolCallLimitMiddleware(
            tool_name="run_sql", run_limit=chat.max_sql_calls_per_turn, exit_behavior="continue"
        ),
        ModelCallLimitMiddleware(run_limit=chat.max_model_calls_per_turn, exit_behavior="end"),
        stop_on_infra_error,
        system_prompt,
    ]
```

Create `apps/api/finance/agent/graph.py`:

```python
"""Assemble the chat agent: one ReAct loop, the run_sql tool and the middleware stack."""

from dataclasses import dataclass

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer

from finance.agent.middleware import build_middleware
from finance.settings import ChatSettings


@dataclass(frozen=True)
class AgentContext:
    """Per-turn runtime context (create_agent's context_schema); never stored in the checkpoint."""

    data_context: str


@dataclass(frozen=True)
class ChatModels:
    agent: BaseChatModel
    summary: BaseChatModel
    title: BaseChatModel


def chat_models(chat: ChatSettings) -> ChatModels:
    """`reasoning_effort` is passed to providers that accept it (xAI, OpenAI)."""
    return ChatModels(
        agent=init_chat_model(
            chat.model, reasoning_effort=chat.reasoning_effort, max_retries=chat.max_retries
        ),
        summary=init_chat_model(
            chat.summary_model,
            reasoning_effort=chat.summary_reasoning_effort,
            max_retries=chat.max_retries,
        ),
        title=init_chat_model(chat.title_model, max_retries=chat.max_retries),
    )


def build_agent(
    models: ChatModels, tools: list[BaseTool], chat: ChatSettings, checkpointer: Checkpointer
):
    return create_agent(
        models.agent,
        tools=tools,
        middleware=build_middleware(chat, models.summary),
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )
```

Facts this relies on (checked against langchain 1.4.4): `before_agent`/`before_model` take `name=` and `can_jump_to=`; a `before_model` hook returning `{"jump_to": "end"}` ends the run without a model call; `dynamic_prompt` may return a `SystemMessage`, and the system message is never written to the checkpoint; `create_agent` sets `recursion_limit=9999`, so the real limits are the two call-limit middlewares.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_agent_graph.py -q && uv run task test`
Expected: 6 passed, then the whole unit suite passes.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/agent/middleware.py apps/api/finance/agent/graph.py apps/api/tests/fakes.py apps/api/tests/test_agent_graph.py
git commit -m "feat: chat agent graph with limits, context editing and summarization"
```

---

### Task 9: The AI SDK stream adapter

**Files:**
- Create: `apps/api/finance/agent/ui_stream.py`
- Test: `apps/api/tests/test_ui_stream.py`

**Interfaces:**
- Consumes: Task 8 (`NOTICE_NODES`, `build_agent`), Task 4 (`QueryResult`).
- Produces: `UI_STREAM_HEADERS`; `TurnRecord(texts, queries, hit_sql_limit)` with `.text` and `.infra_error`; `ui_parts(stream, record) -> AsyncIterator[dict]` (parts `text-start|text-delta|text-end` with ids `text-0`, `text-1`…, `tool-input-available`, `tool-output-available`); `sse(parts) -> AsyncIterator[str]` (`data: <json>\n\n`, then `data: [DONE]\n\n`).

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_ui_stream.py`:

```python
import asyncio

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from finance.agent.graph import AgentContext, ChatModels, build_agent
from finance.agent.middleware import INFRA_MESSAGE
from finance.agent.models import QueryResult
from finance.agent.tools import make_run_sql
from finance.agent.ui_stream import TurnRecord, sse, ui_parts
from finance.settings import ChatSettings
from tests.fakes import ScriptedChatModel, tool_call


def _parts(responses, run_query=None, **chat):
    async def ok(sql):
        return QueryResult(sql=sql, columns=["n"], rows=[["1"]], row_count=1)

    model = ScriptedChatModel(responses=responses)
    tool = make_run_sql(run_query or ok, rows_shown=50, max_chars=8000)
    models = ChatModels(agent=model, summary=model, title=model)
    agent = build_agent(models, [tool], ChatSettings(**chat), InMemorySaver())
    record = TurnRecord()

    async def collect():
        stream = agent.astream(
            {"messages": [HumanMessage("q")]},
            {"configurable": {"thread_id": "t"}},
            context=AgentContext("ctx"),
            stream_mode=["messages", "updates"],
            version="v2",
        )
        return [part async for part in ui_parts(stream, record)]

    return asyncio.run(collect()), record


def test_a_query_and_its_answer_become_tool_and_text_parts():
    parts, record = _parts([tool_call("SELECT 1", "c1"), AIMessage("There is one.")])
    assert [p["type"] for p in parts] == [
        "tool-input-available",
        "tool-output-available",
        "text-start",
        "text-delta",
        "text-end",
    ]
    assert parts[0]["input"] == {"sql": "SELECT 1"} and parts[0]["toolName"] == "run_sql"
    assert parts[1]["output"]["rows"] == [["1"]]
    assert record.text == "There is one." and [q.sql for q in record.queries] == ["SELECT 1"]


def test_text_before_and_after_a_query_is_two_blocks():
    first = AIMessage("Let me check.", tool_calls=tool_call("SELECT 1", "c1").tool_calls)
    parts, record = _parts([first, AIMessage("Done.")])
    starts = [p["id"] for p in parts if p["type"] == "text-start"]
    assert starts == ["text-0", "text-1"] and record.text == "Let me check.\n\nDone."


def test_the_infrastructure_notice_reaches_the_user():
    async def down(sql):
        return QueryResult(sql=sql, error="connection refused", infra_error=True)

    parts, record = _parts([tool_call("SELECT 1", "c1")], down)
    assert record.text == INFRA_MESSAGE and record.infra_error


def test_reaching_the_query_limit_is_recorded():
    calls = [tool_call(f"SELECT {n}", f"c{n}") for n in range(3)]
    _, record = _parts([*calls, AIMessage("Done.")], max_sql_calls_per_turn=2)
    assert record.hit_sql_limit and record.text == "Done."


def test_history_rewrites_are_never_streamed_again():
    async def stream():
        old = AIMessage("an old answer")
        yield {
            "type": "updates",
            "ns": (),
            "data": {
                "SummarizationMiddleware.before_model": {
                    "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), old]
                }
            },
        }

    async def collect():
        return [part async for part in ui_parts(stream(), TurnRecord())]

    assert asyncio.run(collect()) == []


def test_parts_are_encoded_as_server_sent_events_ending_in_done():
    async def parts():
        yield {"type": "text-delta", "id": "text-0", "delta": "año"}

    async def collect():
        return [event async for event in sse(parts())]

    assert asyncio.run(collect()) == [
        'data: {"type": "text-delta", "id": "text-0", "delta": "año"}\n\n',
        "data: [DONE]\n\n",
    ]


def test_text_sent_as_content_blocks_is_streamed_as_text():
    blocks = AIMessage(content=[{"type": "text", "text": "Block answer."}])
    _, record = _parts([blocks])
    assert record.text == "Block answer."
```

They drive a real agent with the scripted model, so node names (`model`, `tools`, `ModelCallLimitMiddleware.before_model`, `stop_on_infra_error.before_model`) are the ones LangGraph emits.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_ui_stream.py -q`
Expected: FAIL (`No module named 'finance.agent.ui_stream'`).

- [ ] **Step 3: Implement**

Create `apps/api/finance/agent/ui_stream.py`:

```python
"""Translate the agent's stream into AI SDK UI message stream parts (spec section 9).

Reads `astream(stream_mode=["messages", "updates"], version="v2")`: text comes from the model's
message chunks, tool calls and results from node updates. Updates that rewrite the history
(summarization, the dangling-call repair) carry a RemoveMessage and are skipped, so old messages
are never streamed again.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, RemoveMessage, ToolMessage

from finance.agent.middleware import NOTICE_NODES
from finance.agent.models import QueryResult

UI_STREAM_HEADERS = {
    "x-vercel-ai-ui-message-stream": "v1",
    "cache-control": "no-cache",
    "x-accel-buffering": "no",
}


@dataclass
class TurnRecord:
    """What a turn produced: the text for chat_messages, the queries and the Langfuse scores."""

    texts: list[str] = field(default_factory=list)
    queries: list[QueryResult] = field(default_factory=list)
    hit_sql_limit: bool = False

    @property
    def text(self) -> str:
        return "\n\n".join(t for t in self.texts if t)

    @property
    def infra_error(self) -> bool:
        return any(q.infra_error for q in self.queries)


async def ui_parts(stream: AsyncIterator[dict], record: TurnRecord) -> AsyncIterator[dict]:
    text_id: str | None = None
    async for part in stream:
        if part["type"] == "messages":
            chunk, metadata = part["data"]
            node = metadata.get("langgraph_node")
            if not isinstance(chunk, AIMessage) or (node != "model" and node not in NOTICE_NODES):
                continue  # the summarizer's own model call streams under its middleware node
            if not chunk.text:
                continue
            if text_id is None:
                text_id = f"text-{len(record.texts)}"
                record.texts.append("")
                yield {"type": "text-start", "id": text_id}
            record.texts[-1] += chunk.text
            yield {"type": "text-delta", "id": text_id, "delta": chunk.text}
            continue
        for node, update in part["data"].items():
            messages = update.get("messages", []) if isinstance(update, dict) else []
            if any(isinstance(m, RemoveMessage) for m in messages):
                continue
            if text_id is not None and node in ("model", "tools"):
                yield {"type": "text-end", "id": text_id}
                text_id = None
            for message in messages:
                if node == "model" and isinstance(message, AIMessage):
                    for call in message.tool_calls:
                        yield {
                            "type": "tool-input-available",
                            "toolCallId": call["id"],
                            "toolName": call["name"],
                            "input": call["args"],
                        }
                elif isinstance(message, ToolMessage):
                    record.hit_sql_limit |= node.startswith("ToolCallLimitMiddleware")
                    if isinstance(message.artifact, dict):
                        record.queries.append(QueryResult(**message.artifact))
                        output = message.artifact
                    else:
                        output = {"error": str(message.content)}
                    yield {
                        "type": "tool-output-available",
                        "toolCallId": message.tool_call_id,
                        "output": output,
                    }
    if text_id is not None:
        yield {"type": "text-end", "id": text_id}


async def sse(parts: AsyncIterator[dict]) -> AsyncIterator[str]:
    """Server-sent events as AI SDK reads them: one JSON part per event, then [DONE]."""
    async for part in parts:
        yield f"data: {json.dumps(part, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"
```

Part shapes follow https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol (read on 2026-10-12). Text is read with `.text`, which joins content blocks; reading `.content` as a string loses answers sent as blocks.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_ui_stream.py -q`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/agent/ui_stream.py apps/api/tests/test_ui_stream.py
git commit -m "feat: stream agent turns in the AI SDK UI message protocol"
```

---

### Task 10: Chat store and titles

**Files:**
- Create: `apps/api/finance/agent/store.py`, `apps/api/finance/agent/title.py`
- Test: `apps/api/tests/test_chat_title.py` (unit). The store is exercised by the integration tests of Tasks 11-13.

**Interfaces:**
- Consumes: `models` (Task 4).
- Produces:
  - `store`: `create_thread(pool) -> Thread`, `list_threads(pool) -> list[Thread]` (newest first), `get_thread(pool, id) -> Thread | None`, `rename_thread(pool, id, title) -> Thread | None` (source `user`), `set_generated_title(pool, id, title, source) -> bool` (only while `title_source` is null), `delete_thread(pool, id) -> bool`, `add_message(pool, thread_id, role, content, *, message_id=None, queries=(), status="ok", trace_id=None) -> UUID` (touches `updated_at`), `list_messages(pool, thread_id) -> list[ChatMessage]`, `set_feedback(pool, message_id, value) -> str | None` (trace id; raises `MessageNotFound`).
  - `title`: `TITLE_INSTRUCTIONS`, `ChatTitle(title)`, `fallback_title(question, max_chars) -> str`, `generate_title(model, question, max_chars, config=None) -> tuple[str, TitleSource]` (`model` returns a `ChatTitle`).

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_chat_title.py`:

```python
import asyncio

from langchain_core.runnables import RunnableLambda

from finance.agent.title import ChatTitle, fallback_title, generate_title


def _title(answer, question="Dame los gastos en super la semana pasada", max_chars=60):
    def respond(messages):
        if isinstance(answer, Exception):
            raise answer
        return ChatTitle(title=answer)

    return asyncio.run(generate_title(RunnableLambda(respond), question, max_chars))


def test_the_model_title_is_cleaned_of_quotes_and_a_final_period():
    assert _title('"Gastos en supermercado."') == ("Gastos en supermercado", "model")


def test_a_failing_or_overlong_title_falls_back_to_the_question():
    assert _title(RuntimeError("provider down")) == (
        "Dame los gastos en super la semana pasada",
        "fallback",
    )
    assert _title("x" * 61)[1] == "fallback"


def test_the_fallback_is_cut_with_an_ellipsis():
    assert fallback_title("  one   two three four  ", max_chars=60) == "one two three four"
    assert fallback_title("a" * 70, max_chars=20) == "a" * 19 + "…"
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_chat_title.py -q`
Expected: FAIL (`No module named 'finance.agent.title'`).

- [ ] **Step 3: Implement**

Create `apps/api/finance/agent/store.py`:

```python
"""Chat threads and the history the user sees (spec section 8). The agent's own memory is the
LangGraph checkpoint; ChatService.delete_thread removes both."""

from uuid import UUID

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from finance.agent.models import (
    ChatMessage,
    Feedback,
    MessageStatus,
    QueryResult,
    Thread,
    TitleSource,
)

_THREAD = "id, title, title_source, created_at, updated_at"
_MESSAGE = "id, thread_id, role, content, queries, status, feedback, created_at"


class MessageNotFound(Exception):
    pass


async def create_thread(pool: AsyncConnectionPool) -> Thread:
    async with pool.connection() as conn:
        cursor = await conn.execute(f"insert into chat_threads default values returning {_THREAD}")
        return Thread(**await cursor.fetchone())


async def list_threads(pool: AsyncConnectionPool) -> list[Thread]:
    async with pool.connection() as conn:
        cursor = await conn.execute(f"select {_THREAD} from chat_threads order by updated_at desc")
        return [Thread(**row) for row in await cursor.fetchall()]


async def get_thread(pool: AsyncConnectionPool, thread_id: UUID) -> Thread | None:
    async with pool.connection() as conn:
        cursor = await conn.execute(
            f"select {_THREAD} from chat_threads where id = %s", (thread_id,)
        )
        row = await cursor.fetchone()
    return Thread(**row) if row else None


async def rename_thread(pool: AsyncConnectionPool, thread_id: UUID, title: str) -> Thread | None:
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "update chat_threads set title = %s, title_source = 'user', updated_at = now()"
            f" where id = %s returning {_THREAD}",
            (title, thread_id),
        )
        row = await cursor.fetchone()
    return Thread(**row) if row else None


async def set_generated_title(
    pool: AsyncConnectionPool, thread_id: UUID, title: str, source: TitleSource
) -> bool:
    """Store a generated title unless the thread already has one (the user may have renamed it)."""
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "update chat_threads set title = %s, title_source = %s"
            " where id = %s and title_source is null returning id",
            (title, source, thread_id),
        )
        return await cursor.fetchone() is not None


async def delete_thread(pool: AsyncConnectionPool, thread_id: UUID) -> bool:
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "delete from chat_threads where id = %s returning id", (thread_id,)
        )
        return await cursor.fetchone() is not None


async def add_message(
    pool: AsyncConnectionPool,
    thread_id: UUID,
    role: str,
    content: str,
    *,
    message_id: UUID | None = None,
    queries: list[QueryResult] = (),
    status: MessageStatus = "ok",
    trace_id: str | None = None,
) -> UUID:
    async with pool.connection() as conn, conn.transaction():
        cursor = await conn.execute(
            "insert into chat_messages (id, thread_id, role, content, queries, status,"
            " langfuse_trace_id) values (coalesce(%s, gen_random_uuid()), %s, %s, %s, %s, %s, %s)"
            " returning id",
            (
                message_id,
                thread_id,
                role,
                content,
                Jsonb([q.model_dump() for q in queries]),
                status,
                trace_id,
            ),
        )
        new_id = (await cursor.fetchone())["id"]
        await conn.execute("update chat_threads set updated_at = now() where id = %s", (thread_id,))
    return new_id


async def list_messages(pool: AsyncConnectionPool, thread_id: UUID) -> list[ChatMessage]:
    async with pool.connection() as conn:
        cursor = await conn.execute(
            f"select {_MESSAGE} from chat_messages where thread_id = %s order by created_at, id",
            (thread_id,),
        )
        return [ChatMessage(**row) for row in await cursor.fetchall()]


async def set_feedback(pool: AsyncConnectionPool, message_id: UUID, value: Feedback) -> str | None:
    """Record thumbs up or down on an answer; return its Langfuse trace id (None if untraced)."""
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "update chat_messages set feedback = %s where id = %s and role = 'assistant'"
            " returning langfuse_trace_id",
            (value, message_id),
        )
        row = await cursor.fetchone()
    if row is None:
        raise MessageNotFound(f"answer {message_id} not found")
    return row["langfuse_trace_id"]
```

Create `apps/api/finance/agent/title.py`:

```python
"""A short title for a new chat, from its first question, by a model without reasoning (spec
section 8). A title is cosmetic: any failure falls back to the question itself."""

import logging

from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel, Field

from finance.agent.models import TitleSource

logger = logging.getLogger(__name__)

TITLE_INSTRUCTIONS = (
    "You name chats about personal finances. Return a title of 3 to 6 words for a chat that "
    "starts with the user's message, in the language of that message, without quotes or a "
    "final period."
)


class ChatTitle(BaseModel):
    """A short title for a chat."""

    title: str = Field(
        description="3 to 6 words in the language of the question, no quotes, no final period"
    )


def fallback_title(question: str, max_chars: int) -> str:
    text = " ".join(question.split())
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


async def generate_title(
    model: Runnable, question: str, max_chars: int, config: RunnableConfig | None = None
) -> tuple[str, TitleSource]:
    """`model` returns a ChatTitle (a chat model's with_structured_output(ChatTitle))."""
    try:
        answer = await model.ainvoke(
            [("system", TITLE_INSTRUCTIONS), ("user", question)], config=config
        )
        title = " ".join(answer.title.strip().strip("\"'“”«»").rstrip(".").split())
        if 0 < len(title) <= max_chars:
            return title, "model"
        logger.warning("chat title of %d characters ignored", len(title))
    except Exception:
        logger.warning("chat title generation failed", exc_info=True)
    return fallback_title(question, max_chars), "fallback"
```

A structured output is the contract for the title: in a check on 2026-10-12 the title model, asked in plain text, answered "**Título sugerido:** … (Otra opción más corta…)".

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_chat_title.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/agent/store.py apps/api/finance/agent/title.py apps/api/tests/test_chat_title.py
git commit -m "feat: chat threads, messages and titles"
```

---

### Task 11: The chat service and runtime

**Files:**
- Create: `apps/api/finance/agent/service.py`, `apps/api/finance/agent/runtime.py`
- Modify: `apps/api/tests/fakes.py`
- Test: `apps/api/tests/test_chat_service.py` (integration)

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `service.ThreadBusy`, `ERROR_TEXT`, `turn_scores(record, status) -> dict[str, tuple[float, str]]`, `ChatService(pool, agent, checkpointer, layer, columns, layer_version, title_model, chat, active)` with `data_context(today=None) -> str`, `stream_turn(thread, text) -> AsyncIterator[dict]` (claims the thread at once or raises `ThreadBusy`; parts start with `start` (`messageId` = the saved answer's id) and end with `finish`; `data-title` on the first turn; `error` with `ERROR_TEXT` on failure), `delete_thread(thread_id) -> bool` (raises `ThreadBusy`).
  - `runtime.open_chat(settings, models=None)` async context manager → `ChatService | None`.
  - `tests/fakes.py`: `title_call(title) -> AIMessage`, `scripted_models(agent_responses, title="Test title") -> ChatModels`.

- [ ] **Step 1: Extend `tests/fakes.py`**

Add `from finance.agent.graph import ChatModels` to the imports, above `from finance.categorization.jev_client import ...`, and append:

```python
def title_call(title: str) -> AIMessage:
    """A scripted title model turn: with_structured_output(ChatTitle) parses this tool call."""
    return AIMessage(
        content="", tool_calls=[{"name": "ChatTitle", "args": {"title": title}, "id": "title"}]
    )


def scripted_models(agent: list[BaseMessage], title: str = "Test title") -> ChatModels:
    """Scripted models for open_chat: the agent (also the summarizer) and a title model."""
    model = ScriptedChatModel(responses=agent)
    return ChatModels(
        agent=model, summary=model, title=ScriptedChatModel(responses=[title_call(title)])
    )
```

- [ ] **Step 2: Write the failing tests**

Create `apps/api/tests/test_chat_service.py`:

```python
import asyncio
import threading

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from finance.agent import store
from finance.agent.graph import ChatModels
from finance.agent.runtime import open_chat
from finance.agent.service import ERROR_TEXT, ThreadBusy
from finance.settings import get_settings
from tests.fakes import ScriptedChatModel, scripted_models, title_call, tool_call

pytestmark = pytest.mark.integration


async def _collect(parts):
    return [part async for part in parts]


def _scenario(models, body):
    """Open the chat with scripted models, run body(chat, thread), delete the thread after."""

    async def go():
        async with open_chat(get_settings(), models) as chat:
            thread = await store.create_thread(chat.pool)
            try:
                return await body(chat, thread)
            finally:
                await chat.delete_thread(thread.id)

    return asyncio.run(go())


def test_a_turn_streams_saves_both_messages_and_titles_the_thread():
    models = scripted_models(
        [tool_call("SELECT count(*) AS n FROM transactions", "c1"), AIMessage("You have some.")],
        title="Counting movements",
    )

    async def body(chat, thread):
        parts = await _collect(chat.stream_turn(thread, "How many movements?"))
        return (
            parts,
            await store.list_messages(chat.pool, thread.id),
            await store.get_thread(chat.pool, thread.id),
        )

    parts, messages, thread = _scenario(models, body)
    kinds = [p["type"] for p in parts]
    assert kinds[0] == "start" and kinds[-1] == "finish"
    assert {"tool-input-available", "tool-output-available", "text-delta", "data-title"} <= set(
        kinds
    )
    assert [(m.role, m.status) for m in messages] == [("user", "ok"), ("assistant", "ok")]
    assert messages[1].content == "You have some."
    assert messages[1].queries[0].columns == ["n"]
    assert str(messages[1].id) == parts[0]["messageId"]
    assert (thread.title, thread.title_source) == ("Counting movements", "model")


def test_a_second_turn_while_answering_is_refused():
    models = scripted_models([AIMessage("One."), AIMessage("Two.")])

    async def body(chat, thread):
        parts = chat.stream_turn(thread, "first")
        with pytest.raises(ThreadBusy):
            chat.stream_turn(thread, "second")
        await _collect(parts)
        return thread.id not in chat.active

    assert _scenario(models, body)


STARTED, GATE = threading.Event(), threading.Event()


class SlowLateAnswer(ScriptedChatModel):
    """Holds the 'late' answer until the test has stopped the turn. It takes its answer before
    waiting, so the cancelled call keeps 'late' and the next turn gets the next answer."""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(list(messages))
        response = self.responses.pop(0)
        if response.content == "late":
            STARTED.set()
            GATE.wait(5)
        return ChatResult(generations=[ChatGeneration(message=response)])


def test_a_stopped_answer_is_saved_as_stopped_and_the_thread_keeps_working():
    agent = SlowLateAnswer(
        responses=[tool_call("SELECT 1 AS n", "c1"), AIMessage("late"), AIMessage("Next answer.")]
    )
    models = ChatModels(
        agent=agent, summary=agent, title=ScriptedChatModel(responses=[title_call("t")])
    )

    async def body(chat, thread):
        parts = chat.stream_turn(thread, "slow question")
        async for part in parts:
            if part["type"] == "tool-output-available":
                break
        await asyncio.to_thread(STARTED.wait, 5)  # the answer is being written
        await parts.aclose()  # what a client disconnect does
        GATE.set()
        refreshed = await store.get_thread(chat.pool, thread.id)
        await _collect(chat.stream_turn(refreshed, "next question"))
        return await store.list_messages(chat.pool, thread.id)

    messages = _scenario(models, body)
    assert [(m.role, m.status) for m in messages] == [
        ("user", "ok"),
        ("assistant", "stopped"),
        ("user", "ok"),
        ("assistant", "ok"),
    ]
    assert messages[1].queries[0].sql == "SELECT 1 AS n"
    assert messages[3].content == "Next answer."


class FailingModel(ScriptedChatModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise RuntimeError("provider exploded")


def test_a_model_failure_ends_with_a_readable_error_and_is_saved():
    models = ChatModels(
        agent=FailingModel(responses=[]),
        summary=FailingModel(responses=[]),
        title=ScriptedChatModel(responses=[title_call("t")]),
    )

    async def body(chat, thread):
        parts = await _collect(chat.stream_turn(thread, "q"))
        return parts, await store.list_messages(chat.pool, thread.id)

    parts, messages = _scenario(models, body)
    assert {"type": "error", "errorText": ERROR_TEXT} in parts
    assert messages[-1].status == "error"


def test_deleting_a_thread_removes_its_checkpoint_and_history():
    models = scripted_models([AIMessage("Hi.")])

    async def go():
        async with open_chat(get_settings(), models) as chat:
            thread = await store.create_thread(chat.pool)
            await _collect(chat.stream_turn(thread, "hello"))
            config = {"configurable": {"thread_id": str(thread.id)}}
            before = await chat.checkpointer.aget_tuple(config)
            assert await chat.delete_thread(thread.id)
            after = await chat.checkpointer.aget_tuple(config)
            return before is not None, after, await store.list_messages(chat.pool, thread.id)

    had_checkpoint, after, messages = asyncio.run(go())
    assert had_checkpoint and after is None and messages == []


def test_a_turn_nobody_reads_still_finishes_saves_and_frees_the_thread():
    models = scripted_models([AIMessage("Saved anyway.")])

    async def body(chat, thread):
        parts = chat.stream_turn(thread, "q")  # the client disconnects before reading anything
        for _ in range(100):
            if thread.id not in chat.active:
                break
            await asyncio.sleep(0.05)
        await parts.aclose()
        return thread.id in chat.active, await store.list_messages(chat.pool, thread.id)

    busy, messages = _scenario(models, body)
    assert not busy and messages[-1].content == "Saved anyway."
```

The stop test cancels while the second model call is in progress; the scripted model takes its answer before blocking, so the cancelled call keeps `late` and the next turn deterministically gets `Next answer.`.

- [ ] **Step 3: Run them to see them fail**

Run: `uv run pytest tests/test_chat_service.py -q -m integration`
Expected: FAIL (`No module named 'finance.agent.runtime'`).

- [ ] **Step 4: Implement**

Create `apps/api/finance/agent/service.py`:

```python
"""One chat turn end to end (spec sections 7-9 and 11): data context, agent stream, AI SDK parts,
title, persistence, Langfuse trace and scores.

The turn runs in its own task and hands parts over a queue. The Langfuse context opens and closes
inside that task, a stopped answer cancels only the task (its partial answer is saved as
`stopped`), and the thread is released even if the client never reads the stream.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID, uuid4

from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from psycopg_pool import AsyncConnectionPool

from finance.agent import store
from finance.agent.catalog import read_catalog
from finance.agent.data_context import render_data_context
from finance.agent.graph import AgentContext
from finance.agent.models import MessageStatus, Thread
from finance.agent.prompt import PROMPT_VERSION
from finance.agent.semantic_layer import SemanticLayer
from finance.agent.title import generate_title
from finance.agent.ui_stream import TurnRecord, ui_parts
from finance.settings import ChatSettings
from finance.tracing import langfuse

logger = logging.getLogger(__name__)

ERROR_TEXT = "Something went wrong while answering. Try again."
_DONE = object()


class ThreadBusy(Exception):
    pass


def turn_scores(record: TurnRecord, status: MessageStatus) -> dict[str, tuple[float, str]]:
    """Deterministic per-turn scores for Langfuse: (value, data type)."""
    return {
        "sql_calls": (float(len(record.queries)), "NUMERIC"),
        "sql_errors": (float(sum(1 for q in record.queries if q.error)), "NUMERIC"),
        "hit_sql_limit": (float(record.hit_sql_limit), "BOOLEAN"),
        "stopped": (float(status == "stopped"), "BOOLEAN"),
        "infra_error": (float(record.infra_error), "BOOLEAN"),
    }


@dataclass
class ChatService:
    pool: AsyncConnectionPool
    agent: CompiledStateGraph
    checkpointer: BaseCheckpointSaver
    layer: SemanticLayer
    columns: dict[str, dict[str, str]]
    layer_version: str
    title_model: Runnable
    chat: ChatSettings
    active: set[UUID] = field(default_factory=set)

    async def data_context(self, today: date | None = None) -> str:
        catalog = await read_catalog(self.pool)
        return render_data_context(self.layer, self.columns, catalog, today or date.today())

    def stream_turn(self, thread: Thread, text: str) -> AsyncIterator[dict]:
        """Start the turn now and return its UI parts. A thread answers one turn at a time."""
        if thread.id in self.active:
            raise ThreadBusy(thread.id)
        self.active.add(thread.id)
        queue: asyncio.Queue = asyncio.Queue()
        message_id = uuid4()
        task = asyncio.create_task(self._turn(thread, text, message_id, queue))
        return self._relay(task, queue, message_id)

    async def delete_thread(self, thread_id: UUID) -> bool:
        if thread_id in self.active:
            raise ThreadBusy(thread_id)
        deleted = await store.delete_thread(self.pool, thread_id)
        await self.checkpointer.adelete_thread(str(thread_id))
        return deleted

    async def _relay(
        self, task: asyncio.Task, queue: asyncio.Queue, message_id: UUID
    ) -> AsyncIterator[dict]:
        try:
            yield {"type": "start", "messageId": str(message_id)}
            while (part := await queue.get()) is not _DONE:
                yield part
            yield {"type": "finish"}
        finally:  # the client left or stopped: cancel the turn, which saves it as stopped
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _turn(
        self, thread: Thread, text: str, message_id: UUID, queue: asyncio.Queue
    ) -> None:
        record, status, trace_id = TurnRecord(), "ok", None
        attributes = {
            "session_id": str(thread.id),
            "user_id": self.chat.user_id,
            "tags": ["chat"],
            "version": PROMPT_VERSION,
            "trace_name": "chat-turn",
            "metadata": {
                "semantic_layer": self.layer_version,
                "model": self.chat.model,
                "reasoning_effort": self.chat.reasoning_effort,
            },
        }
        try:
            with (
                propagate_attributes(**attributes),
                langfuse().start_as_current_observation(
                    as_type="agent", name="chat-turn", input=text
                ) as turn,
            ):
                trace_id = turn.trace_id
                try:
                    await store.add_message(self.pool, thread.id, "user", text)
                    title = None
                    if thread.title_source is None:
                        title = asyncio.create_task(self._title(thread, text, queue))
                    await self._answer(thread, text, record, queue)
                    if title is not None:
                        await title
                except asyncio.CancelledError:
                    status = "stopped"
                    raise
                except Exception:
                    status = "error"
                    logger.exception("chat turn failed")
                    await queue.put({"type": "error", "errorText": ERROR_TEXT})
                finally:
                    if status == "ok" and record.infra_error:
                        status = "error"
                    level = "ERROR" if status == "error" else "DEFAULT"
                    if level == "DEFAULT" and record.hit_sql_limit:
                        level = "WARNING"  # the model answered, with what it had
                    turn.update(output=record.text, level=level, status_message=status)
        finally:
            try:
                await self._save(thread.id, message_id, record, status, trace_id)
            except Exception:
                logger.exception("could not save the chat answer")
            finally:
                self.active.discard(thread.id)
                queue.put_nowait(_DONE)

    async def _answer(
        self, thread: Thread, text: str, record: TurnRecord, queue: asyncio.Queue
    ) -> None:
        context = AgentContext(data_context=await self.data_context())
        config = {
            "configurable": {"thread_id": str(thread.id)},
            "recursion_limit": self.chat.recursion_limit,
            "callbacks": [CallbackHandler()],
        }
        stream = self.agent.astream(
            {"messages": [HumanMessage(text)]},
            config,
            context=context,
            stream_mode=["messages", "updates"],
            version="v2",
        )
        async for part in ui_parts(stream, record):
            await queue.put(part)

    async def _title(self, thread: Thread, text: str, queue: asyncio.Queue) -> None:
        config = {"callbacks": [CallbackHandler()], "run_name": "chat-title"}
        title, source = await generate_title(
            self.title_model, text, self.chat.title_max_chars, config
        )
        if await store.set_generated_title(self.pool, thread.id, title, source):
            await queue.put(
                {"type": "data-title", "data": {"threadId": str(thread.id), "title": title}}
            )

    async def _save(
        self,
        thread_id: UUID,
        message_id: UUID,
        record: TurnRecord,
        status: MessageStatus,
        trace_id: str | None,
    ) -> None:
        await store.add_message(
            self.pool,
            thread_id,
            "assistant",
            record.text,
            message_id=message_id,
            queries=record.queries,
            status=status,
            trace_id=trace_id,
        )
        if trace_id:
            for name, (value, data_type) in turn_scores(record, status).items():
                langfuse().create_score(
                    trace_id=trace_id, name=name, value=value, data_type=data_type
                )
```

Create `apps/api/finance/agent/runtime.py`:

```python
"""Open and close the chat: async pool, validated semantic layer, checkpointer, models, agent.

Used by the API lifespan, `finance chat` and the integration tests.
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from finance.agent.catalog import validate_layer
from finance.agent.graph import ChatModels, build_agent, chat_models
from finance.agent.semantic_layer import layer_version, load_semantic_layer
from finance.agent.service import ChatService
from finance.agent.sql_runner import run_query
from finance.agent.title import ChatTitle
from finance.agent.tools import make_run_sql
from finance.db import async_pool
from finance.settings import Settings
from finance.tracing import langfuse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def open_chat(
    settings: Settings, models: ChatModels | None = None
) -> AsyncIterator[ChatService | None]:
    """Yield the chat, or None when it is not configured (no database URL, or an xAI model
    without XAI_API_KEY): the dashboards keep working and the chat routes answer 503."""
    chat = settings.chat
    if not settings.supabase_db_url:
        logger.warning("chat disabled: SUPABASE_DB_URL is not set")
        yield None
        return
    if models is None:
        if settings.xai_api_key:
            os.environ.setdefault("XAI_API_KEY", settings.xai_api_key)
        if chat.model.startswith("xai:") and not os.environ.get("XAI_API_KEY"):
            logger.warning("chat disabled: XAI_API_KEY is not set")
            yield None
            return
        models = chat_models(chat)
    # The checkpointer README: refuse to deserialize unexpected types from the database.
    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    async with async_pool() as pool:
        layer = load_semantic_layer()
        columns = await validate_layer(pool, layer)  # fails loudly on a mismatch
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        run = partial(
            run_query, pool, row_limit=chat.sql_row_limit, timeout_seconds=chat.sql_timeout_seconds
        )
        tool = make_run_sql(run, rows_shown=chat.sql_rows_shown, max_chars=chat.sql_max_chars)
        try:
            yield ChatService(
                pool=pool,
                agent=build_agent(models, [tool], chat, checkpointer),
                checkpointer=checkpointer,
                layer=layer,
                columns=columns,
                layer_version=layer_version(),
                title_model=models.title.with_structured_output(ChatTitle),
                chat=chat,
            )
        finally:
            langfuse().flush()
```

`AsyncPostgresSaver.setup()` creates `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` and `checkpoint_migrations` in `public` on first start (idempotent; it needs the pool's autocommit for `CREATE INDEX CONCURRENTLY`). Their exposure through the Supabase Data API is covered by the separate RLS task (spec section 15).

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_chat_service.py -q -m integration`
Expected: 6 passed. A logged `chat turn failed` error comes from the failing-model test and is expected.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/agent/service.py apps/api/finance/agent/runtime.py apps/api/tests/fakes.py apps/api/tests/test_chat_service.py
git commit -m "feat: chat service with persisted turns, titles, stop and Langfuse traces"
```

---

### Task 12: Chat API routes and the app lifespan

**Files:**
- Create: `apps/api/finance/api/chat.py`
- Modify: `apps/api/finance/api/main.py`
- Test: `apps/api/tests/test_chat_api.py`

**Interfaces:**
- Consumes: Task 11.
- Produces: routes in spec section 9: `POST /chat/threads` (201 → `Thread`), `GET /chat/threads`, `PATCH /chat/threads/{id}` (`{title}`), `DELETE /chat/threads/{id}` (204; 404; 409 while answering), `GET /chat/threads/{id}/messages` (→ `ChatMessage[]`), `POST /chat/threads/{id}/messages` (`{text}` → `text/event-stream` with `x-vercel-ai-ui-message-stream: v1`; 404; 409), `POST /chat/messages/{id}/feedback` (`{value: "up"|"down", comment?}` → 204; 404). Every route answers 503 when the chat is not configured.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_chat_api.py`:

```python
import asyncio
import json
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from finance.agent.runtime import open_chat
from finance.api.main import app
from finance.settings import get_settings
from tests.fakes import scripted_models, tool_call


def _events(body: str) -> list:
    data = [chunk[len("data: ") :] for chunk in body.split("\n\n") if chunk.startswith("data: ")]
    return [d if d == "[DONE]" else json.loads(d) for d in data]


def test_chat_routes_answer_503_when_the_chat_is_not_configured():
    previous = getattr(app.state, "chat", None)
    app.state.chat = None
    try:
        response = TestClient(app).get("/chat/threads")
    finally:
        app.state.chat = previous
    assert response.status_code == 503 and "XAI_API_KEY" in response.json()["detail"]


def _run(models, body):
    """Run body(client, chat, new_thread) against the app with a chat on scripted models.
    Threads made through new_thread are deleted afterwards, whatever happens."""

    async def go():
        async with open_chat(get_settings(), models) as chat:
            previous = getattr(app.state, "chat", None)
            app.state.chat = chat
            created = []
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:

                async def new_thread() -> dict:
                    thread = (await client.post("/chat/threads")).json()
                    created.append(thread["id"])
                    return thread

                try:
                    return await body(client, chat, new_thread)
                finally:
                    app.state.chat = previous
                    for thread_id in created:
                        await chat.delete_thread(thread_id)

    return asyncio.run(go())


@pytest.mark.integration
def test_a_message_streams_in_the_ai_sdk_protocol_and_lands_in_the_history():
    models = scripted_models(
        [tool_call("SELECT count(*) AS n FROM transactions", "c1"), AIMessage("Some.")],
        title="Movement count",
    )

    async def body(client, chat, new_thread):
        thread = await new_thread()
        response = await client.post(
            f"/chat/threads/{thread['id']}/messages", json={"text": "How many movements?"}
        )
        history = (await client.get(f"/chat/threads/{thread['id']}/messages")).json()
        threads = (await client.get("/chat/threads")).json()
        return response, history, next(t for t in threads if t["id"] == thread["id"])

    response, history, thread = _run(models, body)
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response.text)
    assert events[0]["type"] == "start" and events[-2:] == [{"type": "finish"}, "[DONE]"]
    assert {
        "type": "data-title",
        "data": {"threadId": thread["id"], "title": "Movement count"},
    } in events
    assert [(m["role"], m["content"]) for m in history] == [
        ("user", "How many movements?"),
        ("assistant", "Some."),
    ]
    assert history[1]["queries"][0]["sql"] == "SELECT count(*) AS n FROM transactions"
    assert thread["title"] == "Movement count"


@pytest.mark.integration
def test_threads_can_be_renamed_and_deleted_and_unknown_ones_are_404():
    async def body(client, chat, new_thread):
        thread = await new_thread()
        renamed = await client.patch(f"/chat/threads/{thread['id']}", json={"title": " Trips "})
        deleted = await client.delete(f"/chat/threads/{thread['id']}")
        missing = await client.get(f"/chat/threads/{thread['id']}/messages")
        return renamed.json(), deleted.status_code, missing.status_code

    renamed, deleted, missing = _run(scripted_models([]), body)
    assert (renamed["title"], renamed["title_source"]) == ("Trips", "user")
    assert (deleted, missing) == (204, 404)


@pytest.mark.integration
def test_a_second_message_while_answering_is_409():
    async def body(client, chat, new_thread):
        thread = await new_thread()
        chat.active.add(UUID(thread["id"]))
        try:
            return (
                await client.post(f"/chat/threads/{thread['id']}/messages", json={"text": "q"})
            ).status_code
        finally:
            chat.active.clear()

    assert _run(scripted_models([]), body) == 409


@pytest.mark.integration
def test_feedback_is_stored_on_an_answer_and_unknown_answers_are_404():
    async def body(client, chat, new_thread):
        thread = await new_thread()
        response = await client.post(f"/chat/threads/{thread['id']}/messages", json={"text": "hi"})
        answer_id = _events(response.text)[0]["messageId"]
        sent = await client.post(f"/chat/messages/{answer_id}/feedback", json={"value": "up"})
        history = (await client.get(f"/chat/threads/{thread['id']}/messages")).json()
        unknown = await client.post(
            f"/chat/messages/{thread['id']}/feedback", json={"value": "down"}
        )
        return sent.status_code, history[-1]["feedback"], unknown.status_code

    assert _run(scripted_models([AIMessage("Hello.")]), body) == (204, "up", 404)


@pytest.mark.integration
def test_a_chat_cannot_be_deleted_while_it_answers():
    async def body(client, chat, new_thread):
        thread = await new_thread()
        chat.active.add(UUID(thread["id"]))
        try:
            return (await client.delete(f"/chat/threads/{thread['id']}")).status_code
        finally:
            chat.active.clear()

    assert _run(scripted_models([]), body) == 409
```

The integration tests use `httpx.ASGITransport` inside the same event loop as the chat's async pool (`TestClient` runs the app on another loop, where the pool cannot be used). The transport does not run the lifespan, so the test sets `app.state.chat` itself.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_chat_api.py -q -m "not integration"`
Expected: FAIL (404 for `/chat/threads`).

- [ ] **Step 3: Implement**

Create `apps/api/finance/api/chat.py`:

```python
"""Routes for the chat (spec section 9): threads, history, feedback and the streamed answer in
the AI SDK UI message stream protocol."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from finance.agent import store
from finance.agent.models import ChatMessage, Feedback, Thread
from finance.agent.service import ChatService, ThreadBusy
from finance.agent.ui_stream import UI_STREAM_HEADERS, sse
from finance.tracing import langfuse

router = APIRouter(prefix="/chat", tags=["chat"])

BUSY = "This chat is still answering. Wait for it or stop it first."


def get_chat(request: Request) -> ChatService:
    chat = getattr(request.app.state, "chat", None)
    if chat is None:
        raise HTTPException(
            status_code=503,
            detail="The chat is not configured: set SUPABASE_DB_URL and XAI_API_KEY in .env",
        )
    return chat


Chat = Annotated[ChatService, Depends(get_chat)]


async def _thread(chat: ChatService, thread_id: UUID) -> Thread:
    thread = await store.get_thread(chat.pool, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail=f"chat {thread_id} not found")
    return thread


@router.post("/threads", status_code=201)
async def create_thread(chat: Chat) -> Thread:
    return await store.create_thread(chat.pool)


@router.get("/threads")
async def list_threads(chat: Chat) -> list[Thread]:
    return await store.list_threads(chat.pool)


class RenameThread(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@router.patch("/threads/{thread_id}")
async def rename_thread(thread_id: UUID, body: RenameThread, chat: Chat) -> Thread:
    thread = await store.rename_thread(chat.pool, thread_id, body.title.strip())
    if thread is None:
        raise HTTPException(status_code=404, detail=f"chat {thread_id} not found")
    return thread


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(thread_id: UUID, chat: Chat) -> Response:
    try:
        deleted = await chat.delete_thread(thread_id)
    except ThreadBusy as busy:
        raise HTTPException(status_code=409, detail=BUSY) from busy
    if not deleted:
        raise HTTPException(status_code=404, detail=f"chat {thread_id} not found")
    return Response(status_code=204)


@router.get("/threads/{thread_id}/messages")
async def list_messages(thread_id: UUID, chat: Chat) -> list[ChatMessage]:
    await _thread(chat, thread_id)
    return await store.list_messages(chat.pool, thread_id)


class NewMessage(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/threads/{thread_id}/messages", response_class=StreamingResponse)
async def send_message(thread_id: UUID, body: NewMessage, chat: Chat) -> StreamingResponse:
    thread = await _thread(chat, thread_id)
    try:
        parts = chat.stream_turn(thread, body.text.strip())
    except ThreadBusy as busy:
        raise HTTPException(status_code=409, detail=BUSY) from busy
    return StreamingResponse(sse(parts), media_type="text/event-stream", headers=UI_STREAM_HEADERS)


class FeedbackBody(BaseModel):
    value: Feedback
    comment: str | None = Field(default=None, max_length=1000)


@router.post("/messages/{message_id}/feedback", status_code=204)
async def send_feedback(message_id: UUID, body: FeedbackBody, chat: Chat) -> Response:
    try:
        trace_id = await store.set_feedback(chat.pool, message_id, body.value)
    except store.MessageNotFound as missing:
        raise HTTPException(status_code=404, detail=str(missing)) from missing
    if trace_id:
        langfuse().create_score(
            trace_id=trace_id,
            name="user-feedback",
            value=1.0 if body.value == "up" else 0.0,
            data_type="BOOLEAN",
            comment=body.comment,
        )
    return Response(status_code=204)
```

Replace `apps/api/finance/api/main.py`:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from finance.agent.runtime import open_chat
from finance.api import (
    accounts,
    categories,
    categorize,
    chat,
    dashboard,
    imports,
    merchants,
    review,
    spending,
    transactions,
)
from finance.api.deps import same_origin
from finance.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the chat (pool, checkpointer, validated semantic layer) for the app's lifetime."""
    async with open_chat(get_settings()) as chat_service:
        app.state.chat = chat_service
        yield


app = FastAPI(
    title="personal-finance-agent API",
    version="0.1.0",
    dependencies=[Depends(same_origin)],
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
# A DNS-rebinding page reaches the API under its own host name: refuse any other Host.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=get_settings().trusted_hosts)
app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(categorize.router)
app.include_router(chat.router)
app.include_router(dashboard.router)
app.include_router(imports.router)
app.include_router(merchants.router)
app.include_router(review.router)
app.include_router(spending.router)
app.include_router(transactions.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

The stream uses Starlette's `StreamingResponse` with explicit headers: FastAPI's `EventSourceResponse` drops custom headers, and AI SDK needs `x-vercel-ai-ui-message-stream: v1` (spec amendments).

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_chat_api.py -q -m "not integration" && uv run pytest tests/test_chat_api.py -q -m integration && uv run task test`
Expected: 1 passed, 5 passed, then the whole unit suite passes (existing tests use `TestClient(app)` without a context manager, so the lifespan does not run in them).

- [ ] **Step 5: Smoke the running API**

Run `uv run task api` in one terminal, then:

```bash
curl -s -X POST http://localhost:8000/chat/threads
curl -s http://localhost:8000/chat/threads
```

Expected: a new thread, then a list containing it. Delete it: `curl -s -X DELETE http://localhost:8000/chat/threads/<id>` (204). If the API logs `chat disabled`, check `XAI_API_KEY` in `.env`.

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/api/chat.py apps/api/finance/api/main.py apps/api/tests/test_chat_api.py
git commit -m "feat: chat API with AI SDK streaming, threads and feedback"
```

---

### Task 13: `finance chat`

**Files:**
- Create: `apps/api/finance/agent/cli.py`
- Modify: `apps/api/finance/cli.py`
- Test: `apps/api/tests/test_chat_cli.py`

**Interfaces:**
- Consumes: Task 11 (`open_chat`, `stream_turn`), Task 10 (`store`).
- Produces: `agent.cli.render(part) -> str | None`, `chat_session(questions, thread_id, write, models=None) -> int` (exit code); command `finance chat [QUESTION] [--thread ID]`.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_chat_cli.py`:

```python
import asyncio

import pytest
from langchain_core.messages import AIMessage

from finance.agent import store
from finance.agent.cli import chat_session, render
from finance.agent.runtime import open_chat
from finance.settings import get_settings
from tests.fakes import scripted_models, tool_call


def test_the_terminal_shows_the_answer_each_query_and_its_outcome():
    parts = [
        {"type": "start", "messageId": "m"},
        {
            "type": "tool-input-available",
            "toolCallId": "c",
            "toolName": "run_sql",
            "input": {"sql": " SELECT 1 "},
        },
        {"type": "tool-output-available", "toolCallId": "c", "output": {"row_count": 1}},
        {"type": "text-start", "id": "text-0"},
        {"type": "text-delta", "id": "text-0", "delta": "One."},
        {"type": "text-end", "id": "text-0"},
        {"type": "tool-output-available", "toolCallId": "d", "output": {"error": "bad column"}},
        {"type": "error", "errorText": "Something went wrong."},
    ]
    shown = "".join(text for part in parts if (text := render(part)) is not None)
    assert shown == (
        "\n[query]\nSELECT 1\n[1 rows]\nOne.\n[query failed] bad column\n"
        "[error] Something went wrong.\n"
    )


@pytest.mark.integration
def test_a_cli_session_answers_and_keeps_its_thread():
    written: list[str] = []
    models = scripted_models([tool_call("SELECT 1 AS n", "c1"), AIMessage("One.")])
    code = asyncio.run(chat_session(["how many?"], None, written.append, models))
    output = "".join(written)
    thread_id = output.splitlines()[0].removeprefix("chat ")

    async def cleanup():
        async with open_chat(get_settings(), scripted_models([])) as chat:
            messages = await store.list_messages(chat.pool, thread_id)
            await chat.delete_thread(thread_id)
            return messages

    assert code == 0 and "[query]\nSELECT 1 AS n" in output and "One." in output
    assert [m.role for m in asyncio.run(cleanup())] == ["user", "assistant"]
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_chat_cli.py -q -m "not integration"`
Expected: FAIL (`No module named 'finance.agent.cli'`).

- [ ] **Step 3: Implement**

Create `apps/api/finance/agent/cli.py`:

```python
"""`finance chat`: the web chat's agent in the terminal, on the same threads."""

from collections.abc import Callable
from uuid import UUID

from finance.agent import store
from finance.agent.graph import ChatModels
from finance.agent.runtime import open_chat
from finance.settings import get_settings


def render(part: dict) -> str | None:
    """What the terminal shows for one stream part: the answer, each query and its outcome."""
    kind = part["type"]
    if kind == "text-delta":
        return part["delta"]
    if kind == "text-end":
        return "\n"
    if kind == "tool-input-available":
        return f"\n[query]\n{part['input'].get('sql', '').strip()}\n"
    if kind == "tool-output-available":
        output = part["output"]
        if output.get("error"):
            return f"[query failed] {output['error']}\n"
        return f"[{output.get('row_count', 0)} rows]\n"
    if kind == "data-title":
        return f"[title] {part['data']['title']}\n"
    if kind == "error":
        return f"[error] {part['errorText']}\n"
    return None


async def chat_session(
    questions: list[str] | Callable[[], str | None],
    thread_id: UUID | None,
    write: Callable[[str], None],
    models: ChatModels | None = None,
) -> int:
    """Answer each question (a list, or a reader that returns None to stop); 1 if the chat is
    not configured or the thread does not exist."""
    async with open_chat(get_settings(), models) as chat:
        if chat is None:
            write("The chat is not configured: set SUPABASE_DB_URL and XAI_API_KEY in .env\n")
            return 1
        thread = (
            await store.get_thread(chat.pool, thread_id)
            if thread_id
            else await store.create_thread(chat.pool)
        )
        if thread is None:
            write(f"chat {thread_id} not found\n")
            return 1
        write(f"chat {thread.id}\n")
        pending = iter(questions) if isinstance(questions, list) else iter(questions, None)
        for question in pending:
            async for part in chat.stream_turn(thread, question):
                if (text := render(part)) is not None:
                    write(text)
            thread = await store.get_thread(chat.pool, thread.id)  # it may have a title now
    return 0
```

In `apps/api/finance/cli.py`, add `import asyncio` and `from uuid import UUID` to the standard-library imports, `from finance.agent.cli import chat_session` above `from finance.categorization.seed import ...`, and append:

```python
def _read_question() -> str | None:
    try:
        question = input("> ").strip()
    except EOFError:
        return None
    return question or None


@app.command("chat")
def chat_command(
    question: str | None = typer.Argument(
        None, help="Ask once; without it, ask until an empty line"
    ),
    thread: UUID | None = typer.Option(None, help="Continue this chat id"),
) -> None:
    """Ask questions about your data: the web chat's agent, in the terminal."""
    questions = [question] if question else _read_question
    code = asyncio.run(chat_session(questions, thread, lambda text: typer.echo(text, nl=False)))
    raise typer.Exit(code=code)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_chat_cli.py -q -m "not integration" && uv run pytest tests/test_chat_cli.py -q -m integration && uv run finance chat --help`
Expected: 1 passed, 1 passed, and the help lists `[question]` and `--thread`.

- [ ] **Step 5: Run everything**

Run: `uv run task format && uv run task lint && uv run task test && uv run task test-integration`
Expected: lint clean; all unit and integration tests pass (two raw-PDF tests may be skipped).

- [ ] **Step 6: Commit**

```bash
git add apps/api/finance/agent/cli.py apps/api/finance/cli.py apps/api/tests/test_chat_cli.py
git commit -m "feat: finance chat command"
```

---

### Task 14: Documentation and generated web types

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `docs/backlog.md`
- Modify: `apps/web/src/lib/api-types.ts` (generated)

- [ ] **Step 1: README**

- In "Status": slices 1-3 complete; slice 4a (the chat agent backend: API and `finance chat`) complete; the `/chat` page comes next (4b).
- In "Local setup": after `finance seed`, say that `XAI_API_KEY` enables the chat, and that an existing database gets new migrations with `supabase migration up` (never `db reset` with labels you care about).
- Add a section "## How the chat agent answers" after the jev section, generic (no personal data), covering: one ReAct agent (LangChain `create_agent`) with one tool, `run_sql`; the `agent` schema and the read-only `agent_reader` role (guard + role + read-only transaction); the semantic layer in `apps/api/finance/agent/semantic/` (knowledge and attributes, allowed values only for app-defined values, metrics and examples validated with `EXPLAIN` at startup); the static instructions and the per-turn data context; notes explored by reading their values; middleware (summary at 150k tokens, old results cleared, query and model call limits); persistence (checkpointer + `chat_threads`/`chat_messages`); Langfuse (a trace per turn, session per chat, prompt and semantic-layer versions, scores, feedback); `finance chat` usage; the `CHAT__*` settings. Link the spec. Keep jev's section as it is: the chat does not use jev.

- [ ] **Step 2: CLAUDE.md**

- In "Commands", add: `cd apps/api && uv run finance chat ["question"] [--thread ID]   # the chat agent in the terminal (xAI spend)`.
- In "Boundaries", change "jev (`typesafe-sdk`) is used only where the spec says: transaction categorization and the chat router." to "jev (`typesafe-sdk`) is used only for transaction categorization; the chat agent is an LLM (grok) over the semantic layer."
- In "Boundaries", add: "The chat agent reads only the `agent` schema, as `agent_reader` in a read-only transaction; never widen its grants."

- [ ] **Step 3: docs/backlog.md**

Append two ideas:

```markdown
## 5. Account balances in the chat

The agent cannot answer "how much do I have in my account" yet: `balance_after` is stored but
the order of movements within a day is not, so "the balance on a date" could pick the wrong
row. Store each movement's position in its statement at import, then expose the balance per
account and date in the `agent` schema. (Slice 4 spec, section 15.)

## 6. Chat evals

A golden set of questions with reference SQL, run against the agent with repeats (consistent,
flaky, failing), to measure prompt, semantic-layer and model changes. Start from Langfuse
traces of real use (a dataset per version). Include the money rules a model gets wrong, such as
a category total that nets a refund against its purchase.
```

- [ ] **Step 4: Regenerate the web types**

With the API running (`uv run task api`): `cd apps/web && npm run gen:api`
Expected: `src/lib/api-types.ts` gains the `/chat/...` paths and the `Thread`, `ChatMessage`, `QueryResult` schemas. Run `npm run lint && npx tsc --noEmit` in `apps/web`: clean.

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md docs/backlog.md apps/web/src/lib/api-types.ts
git commit -m "docs: the chat agent in the README, project instructions and backlog"
```

---

### Task 15: Live verification with Raul (paid model calls)

Ask Raul before starting: this task spends xAI credit (a few cents per question) and reads his real data. Nothing from it is committed.

- [ ] **Step 1: Prepare**

- Raul adds three or four notes on real movements in `/transactions` (for example an item bought, a trip, a dinner), because the ledger has no notes yet.
- In Langfuse, add a model definition for `grok-4.7` with its prices (input, cached input, output per million tokens from the xAI console) so traces show cost.
- Start the API and confirm the log has no `chat disabled` line.

- [ ] **Step 2: Run the smoke set**

With `uv run finance chat`, one question at a time (Raul picks the wording; the set covers spec section 1):

1. a total for a recent period ("¿cuánto gasté el mes pasado?");
2. a merchant by an approximate name;
3. a question answered through a note;
4. a comparison of two months by group;
5. active subscriptions and their monthly cost;
6. a loan (received, instalments, repaid);
7. a period after the data ends ("¿y esta semana?");
8. an out-of-scope request ("¿en qué fondo invierto?");
9. a follow-up in the same chat ("¿y el anterior?");
10. a category total that includes a refund (check the explanation nets the refund correctly; the validation run got this wrong once).

For each answer, compare the numbers with the dashboard pages, and check the format (key number first, "Cómo lo he contado", the language of the question).

- [ ] **Step 3: Review the traces**

In Langfuse, for each turn: the session groups the chat; the trace carries `version` (prompt hash) and the semantic-layer hash; the scores `sql_calls`, `sql_errors`, `hit_sql_limit`, `stopped`, `infra_error` are present; cost and latency are visible; the title is its own observation.

- [ ] **Step 4: Record the outcome**

Write the findings for Raul in the chat (not in the repo): which questions passed, which failed and why (prompt, semantic layer, model). Fixes that change the prompt or the YAML go through their own small change with Raul's approval; each one is checked again with the same question.
