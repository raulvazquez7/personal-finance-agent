# Slice 4 — the chat agent

Date: 2026-10-12
Status: draft for Raul's review
Owner: Raul Vazquez
Amends: `2026-09-22-personal-finance-agent-v1-design.md` (sections listed in 16)
Inputs: the brainstorm of 2026-10-11 and 2026-10-12; a review of the Simon repository
(a former employer's conversational-analytics agent: generic lessons only, no code, prompt
text or domain logic reused); the LangChain 1.4, LangGraph 1.2, langgraph-checkpoint-postgres
3.1, Langfuse 4.17, xAI and AI SDK documentation read on those dates.

Slice 4 lets the user ask questions about their own bank data in a chat. One agent answers
by writing read-only SQL over a small, well-described data model, keeps every conversation,
and is traced in Langfuse from the first call. It must be as easy to set up as the rest of
the app: clone, `supabase start`, fill the API keys, run.

## 1. Goals and success criteria

1. **Answers an analyst would trust.** The agent knows the data model as an analyst would
   (what each view is for, what each column means, which values exist and what period the
   data covers) and answers with a number it queried in that turn, plus how it counted it.
2. **The user's notes are first-class.** A note the user wrote on a movement ("móvil",
   "Rome trip") is how the agent finds what was bought or why.
3. **Production-grade conversations.** Every thread is stored, listed, renamed, deleted and
   reopened with its full history; a stopped answer or a database outage never breaks a
   thread.
4. **Zero manual database setup.** Everything comes from migrations, with one database URL,
   the same locally and on a hosted Supabase project.
5. **Observable from day one.** One Langfuse trace per turn, grouped by conversation, with
   the prompt and semantic-layer versions, deterministic scores and user feedback.

Slice 4 is done when:

- unit and integration tests in section 13 pass, and lint, types and build are green;
- `finance chat` answers a manual smoke set chosen by Raul (a total for a period, a merchant
  found by an approximate name, a question answered through a note, a comparison,
  subscriptions, a loan, a period after the data ends, an out-of-scope request) with numbers
  that match the dashboards, and each turn's trace shows the session, versions, scores and
  cost in Langfuse;
- a stopped turn and a turn with the database down both leave the thread usable (tests);
- `/chat` has passed an `agent-browser` core check, and one dogfood pass covers the app.

No golden dataset or eval harness is built in this slice (section 15).

## 2. Decisions at a glance

| Topic | Decision |
|---|---|
| Topology | One ReAct agent (`langchain.agents.create_agent`), no router, one tool (`run_sql`) |
| What the agent reads | Schema `agent` with two views over the slice 3 views: `transactions`, `subscriptions` |
| Read-only guarantee | Role `agent_reader` (no login) set per query with `SET LOCAL ROLE`, in a read-only transaction with a timeout; `sqlglot` guard as a second layer |
| Semantic layer | YAML in the repo (model knowledge and attributes, metrics, query examples); column types and app-defined values read from the database |
| Prompt | Static instructions file plus a data context built every turn and passed as runtime `context`; both joined only at model-call time |
| Models | `xai:grok-4.7` with reasoning `high` (agent) and `medium` (summaries); `xai:grok-4.20-non-reasoning` for chat titles |
| Context management | `SummarizationMiddleware` at 150,000 tokens; `ClearToolUsesEdit` for old query results |
| Persistence | LangGraph `AsyncPostgresSaver` (agent memory), `chat_threads`, `chat_messages` (what the user sees) |
| Streaming | AI SDK UI message stream protocol from FastAPI; the web uses `useChat` with its own small components on the existing Base UI kit |
| Observability | Langfuse trace per turn, session per thread, versions, scores, user feedback |
| Settings | A nested `chat` group in the existing `Settings` |

## 3. Architecture

```
web /chat (useChat, own components)        finance chat (CLI)
        │ POST /chat/threads/{id}/messages        │
        ▼                                         ▼
FastAPI chat router ──▶ chat service ──▶ create_agent(model, [run_sql], middleware, checkpointer)
        │ AI SDK SSE        │                     │            │
        │                   │ builds AgentContext  │            └─▶ AsyncPostgresSaver (thread memory)
        │                   │ (data context)       ▼
        │                   │              run_sql ──▶ read-only tx, SET LOCAL ROLE agent_reader
        │                   │                                   └─▶ agent.transactions / agent.subscriptions
        │                   └─▶ chat_threads, chat_messages, title task
        └── Langfuse: chat-turn trace (session = thread)
```

Code lives in `apps/api/finance/agent/` (one responsibility per module: semantic layer,
data context, prompt, SQL guard, SQL execution, tool, middleware, agent factory, chat store,
title, stream adapter) and `apps/api/finance/api/chat.py`. The plan fixes the file list.

## 4. Data surface

### 4.1 Schema `agent`

One migration (`<timestamp>_slice4_chat.sql`) creates the schema and two views. They are
thin projections of the slice 3 views, so the money rules stay in one place
(`v_transactions_enriched`, `docs/money-rules.md`).

| View | Source | Columns |
|---|---|---|
| `agent.transactions` | `v_transactions_enriched` | `booked_at`, `month`, `account`, `bank`, `amount`, `direction`, `tx_type`, `spend`, `income`, `category`, `category_group`, `merchant`, `bank_text`, `bank_operation`, `note`, `is_subscription`, `needs_review` |
| `agent.subscriptions` | `v_subscriptions` | `merchant`, `charges`, `last_charge`, `typical_amount`, `cadence`, `monthly_equivalent`, `active` |

- `category` and `category_group` are `coalesce(..., 'uncategorized')`: a movement without a
  category is never `NULL`, so `category <> 'x'` and `GROUP BY` behave. The value
  `'uncategorized'` (no category yet) is different from the category `uncategorized_expense`
  (categorized as an unknown expense); the data context explains both.
- Not exposed: ids, `description_raw` (it can hold a full card number), IBANs,
  `transfer_pair_id`, confidences and probabilities. Names beat UUIDs for the model.
- The views keep the default owner privileges, so `agent_reader` reads them without any
  right on the base tables. The `agent` schema is not exposed through the Supabase Data API.
  When authentication arrives (v2), the views move to `security_invoker` with row-level
  security on the base tables.
- Account balances are not exposed: the order of movements within a day is not stored, so
  "the balance on a date" could pick the wrong row (section 15).

### 4.2 Role and execution

The same migration creates `agent_reader` (`NOLOGIN`), grants it `USAGE` on `agent` and
`SELECT` on its views, and grants the role to the migrating user (`CURRENT_USER`) with the
`SET` option. Postgres 17 needs that explicit grant: `createrole_self_grant` is empty on
Supabase, so the creator of a role cannot `SET ROLE` to it otherwise.

Every agent query runs on the chat module's connection pool, in its own transaction:

```sql
SET TRANSACTION READ ONLY;
SET LOCAL ROLE agent_reader;
SET LOCAL search_path = agent;
SET LOCAL statement_timeout = '<chat.sql_timeout_seconds>s';
<guarded query>
```

This is the pattern Supabase itself uses (one login, a role switched per request). There is
no second login, password or URL: `SUPABASE_DB_URL_READONLY` leaves `.env.example`. A
`SELECT` can reset the role with `set_config`, or with a built-in that runs SQL from a string
(`query_to_xml`, `ts_stat`), so the guard in section 7.2 rejects `set_config` and every function
it does not recognise unless allowlisted; if the guard failed anyway, the transaction is still
read-only.

### 4.3 Setup for a new user

1. `supabase start` (applies every migration, including the schema, the views and the role).
2. Copy `.env.example` to `.env`; fill `XAI_API_KEY` and `TYPESAFE_API_KEY` (Langfuse keys are
   optional; without them nothing is recorded). The local `SUPABASE_DB_URL` is in the example.
3. `uv sync`, `finance seed`, `finance import <pdf>`, `finance categorize`.
4. `uv run task api` and `npm run dev`. The API creates the checkpoint tables on startup
   (`AsyncPostgresSaver.setup()` is idempotent).

On a hosted Supabase project `SUPABASE_DB_URL` is the session pooler URL (IPv4, prepared
statements work); the transaction pooler would break the API's existing pool. Exposing the
`public` tables through the Data API is a separate, project-wide issue (section 15).

## 5. Semantic layer

### 5.1 Files

`apps/api/finance/agent/semantic/`:

| File | Content |
|---|---|
| `transactions.yaml`, `subscriptions.yaml` | one model each: knowledge and attributes (Appendix B) |
| `metrics.yaml` | metric definitions: name, description, SQL expression, model |
| `examples.yaml` | query examples from easy to complex: question, what it teaches, and the SQL as a list of steps (a lookup comes before the final query) |

The shape follows Simon's `client_data_models`, simplified: the fields that only served its
router (intent signals, example questions per model) are gone, and its `metric`,
`groupable`, `categorical`, `allowed_values` and `source_dimension` collapse into `kind` and
`allowed_values`.

**Model knowledge**: `model`, `description` (what one row is and what it is for), `grain`,
`use_for`, `not_for` (with the alternative).

**Attributes**: `attribute`, `kind`, `description`, optional `allowed_values`. The data type
is read from Postgres, never written by hand. Descriptions are complete and unambiguous,
written from the agent's side: what the column means, how to filter it, what it is not, and
how it relates to other columns.

| `kind` | Meaning for the agent |
|---|---|
| `measure` | a number to aggregate in totals (shown as is when listing); never in `GROUP BY` |
| `dimension` | a value to group or filter by; with allowed values use them as they are, without them look up the exact stored values first |
| `time` | a date or period to filter and group by |
| `text` | free text to search and read; grouped only to list its distinct values, never as an answer's breakdown |
| `flag` | a boolean filter |

**Allowed values** only for what the app defines, so nobody maintains lists of user data:

| Column | Source |
|---|---|
| `bank`, `direction`, `tx_type`, `cadence` | written in the YAML (fixed by code and check constraints) |
| `category` | the `categories` table (the app's taxonomy, seeded from `supabase/seed/categories.yaml`): slug, group, type, `what`, `not_for`; plus `'uncategorized'` |
| `category_group` | the `categories` table: each group and the categories in it |
| `account` | the `accounts` table: name, bank and statement coverage (first `period_start` and last `period_end` in `imports`) |

Merchants, bank texts, bank operations and notes carry no values: the agent explores them.

### 5.2 Metrics and examples

Metric definitions and query examples depend on column names, so they live with the views,
not in the instructions. They teach; they are not a closed catalog.

`metrics.yaml`: `expenses` (`SUM(spend)`), `income` (`SUM(income)`), `savings`
(`SUM(income) - SUM(spend)`), `savings_rate` (`(SUM(income) - SUM(spend)) /
NULLIF(SUM(income), 0)`, computed after summing every account and month, never summed or
averaged), `net_cash_flow` (`SUM(amount)`: how much the selected accounts grew or shrank,
transfers included; never spending).

`examples.yaml`, each with the pattern it teaches, using made-up merchants:

1. Spending in one month: `SUM(spend)` and a whole-month filter.
2. Spending by group in a period, ranked, with each group's share (window function).
3. Income, expenses, savings and savings rate per month, rate after summing, the partial
   month marked.
4. A merchant in two steps: look up the exact name, then total, number of charges and
   average ticket.
5. A note in two steps: list the distinct notes with counts, dates and spend, pick by
   meaning, then list the movements with their notes.
6. This month against the previous one by group: both values, absolute and % change in SQL,
   safe with a zero baseline.
7. Average monthly spending over complete months only, using the coverage.
8. Top merchants inside a category with their share.
9. Active subscriptions and their monthly cost.
10. Loans: money received, instalments, paying account and total repaid.
11. The share of a period that is uncategorized or pending review.
12. Grouped totals that carry the notes of their rows (`string_agg(DISTINCT note, '; ')`).

### 5.3 Loading and validation

At API startup (and at `finance chat` start) the loader reads the YAML, reads column types
from `information_schema`, and fails loudly when:

- an attribute is not a column of its view, or a view column has no attribute;
- a `kind` or `allowed_values` source is unknown;
- a metric or an example step does not pass the SQL guard or does not compile: each runs as
  `EXPLAIN` under `agent_reader`, so a changed view can never leave the agent with broken
  patterns.

### 5.4 The data context

Built at the start of every turn: the loaded YAML plus two small queries (taxonomy; accounts
with coverage) plus today's date. Rendered as compact text, in this order: data model
(knowledge and attributes with their values; each account value carries its coverage) →
metrics → query examples → now (today with its weekday, and the latest imported date).
About 6,000 tokens on the real taxonomy (measured on 2026-10-12). A snapshot
test fixes the rendered text for a fake taxonomy and fake accounts, so a rendering bug cannot
silently drop attributes (it happened in Simon).

## 6. Instructions

`apps/api/finance/agent/prompts/system.md` is static and names no table and only the money
columns spend, income and amount: it says how to work. The draft reviewed in the brainstorm is
Appendix A. Its sections:

- **Role and scope**: answers questions about the user's own bank data with `run_sql`.
  Greetings get one line; anything else (advice, general knowledge, changing data) gets one
  sentence and two or three questions it can answer; data changes point to the Review or
  Transactions page.
- **Rule priority**: data integrity, money rules, numeric correctness, clarity, style.
- **Invariants**: every number comes from a query in this turn (earlier results may be
  cleared); spending uses `spend`, income uses `income`; rates after summing; filter values
  come from allowed values or a lookup; never widen the scope silently.
- **Workflow**: understand → resolve the period → resolve every filter (allowed values;
  lookup queries for open dimensions; read the distinct notes and choose by meaning) → one
  query with totals, shares and deltas in SQL, notes included when listing → check before
  running → recover from errors (two attempts, then explain and offer a related question) →
  answer. Lookups for different filters may run in parallel; the final query runs after them.
- **Clarifying**: one short question with options, only when the ambiguity survives the
  values and lookups and the readings differ materially.
- **Dates**: relative periods against today ("last week" is the previous Monday to Sunday);
  a month without a year is the latest one that started; periods after the coverage are
  stated as such; months without data are "no data", never zero; monthly averages use
  complete months.
- **Comparisons**: same metric, filters and length on both sides; both values, absolute and %
  change in SQL by default; no % on a zero baseline; a partial period is compared with the
  same number of days before it.
- **No data**: check case and accents, the value, the period and the filters before saying
  nothing matches; then say what was searched and offer a next step.
- **Answer format**: the user's language; the key number first; a short list or a table of at
  most 12 rows; "How I counted it" in at most three bullets (dates, accounts, what is in or
  out); money with two decimals in the reader's format; spending as a positive amount; no
  table, column, SQL or tool names and no narrated steps (the app shows the queries); no
  charts or files.
- **Reading the data context**: the kinds, the metrics as definitions, the examples as
  patterns.

## 7. The agent

### 7.1 Assembly

```python
agent = create_agent(
    model=init_chat_model(settings.chat.model, reasoning_effort=..., max_retries=...),
    tools=[run_sql],
    middleware=[...],             # section 7.3, in this order
    context_schema=AgentContext,  # data_context, today, thread_id
    checkpointer=checkpointer,
)
agent.astream({"messages": [user_message]},
              {"configurable": {"thread_id": thread_id}, "recursion_limit": ...,
               "callbacks": [langfuse_handler]},
              context=AgentContext(...), stream_mode=["messages", "updates"], version="v2")
```

- `context=` (runtime context) carries the per-turn data; `config["configurable"]` carries
  only the thread id. LangGraph's `config_schema` is deprecated in favour of
  `context_schema`.
- A `@dynamic_prompt` middleware builds the system message on every model call with two
  content blocks: the instructions (identical every turn, so the provider caches them) and
  `runtime.context.data_context`. The system message is never stored in the checkpoint, so
  changing the prompt or the semantic layer never breaks existing threads.

### 7.2 `run_sql`

One parameter, `sql: str`. Its description says it runs one read-only PostgreSQL `SELECT`
over `transactions` and `subscriptions`, for lookups and for final queries.

1. **Guard** (`sqlglot`, Postgres dialect; a pure function): exactly one statement; the whole
   tree, not only the root, contains read nodes only (any write, DDL, `SET` or `COPY`
   anywhere, CTEs included, is rejected); table references are `transactions`,
   `subscriptions` or CTE names, without a schema; functions `set_config`, `pg_sleep*`,
   `dblink*`, `pg_read*` and `lo_*` are rejected, and so is any function `sqlglot` does not
   recognise unless it is in a short allowlist of pure built-ins (`age`, `make_date`) and has
   no schema. No keyword regex on the raw text (it would
   reject literals such as `'%drop%'`). The query is wrapped in `LIMIT <row_limit + 1>` to
   detect truncation.
2. **Execution** as in section 4.2.
3. **Content for the model**: the row count, then a compact `|`-separated table (plain
   numbers, ISO dates, empty for `NULL`), capped at `sql_rows_shown` rows and `sql_max_chars`
   characters, with a footer when cut ("showing 50 of more than 200 rows: aggregate, filter
   or add ORDER BY … LIMIT").
4. **Artifact** (`ToolMessage.artifact`, not sent to the model): SQL, columns, rows, row
   count, truncated, duration, error. The UI's query disclosure, `chat_messages` and
   Langfuse read it.

The tool never raises:

| Failure | Example | The model receives | Then |
|---|---|---|---|
| Guard rejection | `UPDATE`, unknown table, `set_config` | the reason and a hint | the model fixes it |
| SQL error | unknown column, bad `GROUP BY`, bad cast | the first line of the Postgres error and a hint per error class | the model fixes it |
| Timeout | over `sql_timeout_seconds` | "too slow: aggregate more or narrow the period" | the model fixes it |
| Infrastructure | database down, pool exhausted | a tool message marked as an infrastructure failure | the turn ends with a fixed message, no further LLM call |

### 7.3 Middleware, in order

| # | Middleware | Settings | Purpose |
|---|---|---|---|
| 1 | Close dangling tool calls (own, `@before_agent`, about 15 lines; same logic as `deepagents`' `PatchToolCallsMiddleware`, not worth that dependency) | — | a stopped turn never breaks the thread |
| 2 | `SummarizationMiddleware` | `summary_model` with `medium` reasoning; trigger `("tokens", 150_000)`; keep the last 20 messages; own summary prompt; `trim_tokens_to_summarize` large enough to include the previous summary | long threads |
| 3 | `ContextEditingMiddleware` with `ClearToolUsesEdit` | trigger 15,000 tokens; keep the 4 latest results; keep tool inputs (the SQL); placeholder "result cleared: run the query again if you need these numbers" | old results leave the request, not the state |
| 4 | `ToolCallLimitMiddleware` | `tool_name="run_sql"`, `run_limit=8`, `exit_behavior="continue"` | after 8 queries the model answers with what it has |
| 5 | `ModelCallLimitMiddleware` | `run_limit=12`, `exit_behavior="end"` | hard stop |
| 6 | Stop on infrastructure failure (own, `before_model` with `jump_to: "end"`) | — | fixed message without an LLM call |
| 7 | `@dynamic_prompt` | — | the two system blocks |

The summary prompt keeps what an analysis needs: the user's questions, the periods and
filters used, values already resolved (exact merchant names, notes), figures already given
with their period, and agreed definitions.

Retries: the model client's own `max_retries` for 429 and 5xx (one retry layer); after that
the turn fails visibly. `create_agent` compiles with `recursion_limit=9999`; a lower value is
passed in `config` as a backstop and `GraphRecursionError` is caught. The real limits are
middleware 4 and 5.

Left out on purpose: `ModelRetryMiddleware` (it would double the client's retries),
`ModelFallbackMiddleware` (one provider), `PIIMiddleware` (the views hide IBANs and card
numbers), `HumanInTheLoopMiddleware` (read-only), `TodoListMiddleware` and
`LLMToolSelectorMiddleware` (one tool), `ToolRetryMiddleware` (SQL errors go back to the
model; infrastructure failures stop).

### 7.4 Models

| Use | Model | Reasoning |
|---|---|---|
| Agent | `xai:grok-4.7` | `high` |
| Summaries | `xai:grok-4.7` | `medium` |
| Chat titles | `xai:grok-4.20-non-reasoning` | none (`grok-4.7` cannot turn reasoning off) |

Checked on 2026-10-12 against the xAI API: `grok-4.7` accepts `reasoning_effort`
(`low`, `medium`, `high`, `xhigh`) on chat completions, which `ChatXAI` uses. All model
strings and efforts are settings; another provider is its LangChain package plus its key.
Latency with `high` is the known cost (a turn makes two or three model calls); lowering it is
one setting.

## 8. Persistence and conversations

| Piece | Holds | Why |
|---|---|---|
| `AsyncPostgresSaver` (tables created by `setup()` at startup) | the agent's memory: every message of the thread, tool calls included | what the agent reads to continue; `thread_id` is the chat id |
| `chat_threads` | `id`, `title`, `title_source` (`model`, `fallback`, `user`), `created_at`, `updated_at` | open-source LangGraph has no thread listing |
| `chat_messages` | `id`, `thread_id`, `role`, `content`, `queries` (SQL with row count or error), `status` (`ok`, `error`, `stopped`), `feedback` (`up`, `down`), `langfuse_trace_id`, `created_at` | summarization rewrites the checkpoint; the history the user sees never shrinks, does not depend on LangGraph's internal format, and links each answer to its trace |

The checkpointer gets its own async pool (`autocommit`, `dict_row`, `prepare_threshold=0`,
opened in the API lifespan); `run_sql` and the data-context queries use the same pool with
explicit transactions. The existing sync pool keeps serving the rest of the API.

- **Operations**: create, list (newest first), open with full history, rename, delete (the
  checkpoint with `adelete_thread` and both tables).
- **Stop**: a client disconnect cancels the turn; the text produced so far is saved with
  status `stopped`; a tool call left without a result is closed by middleware 1 on the next
  turn. Covered by a regression test.
- **One turn at a time per thread**: a second message while one is streaming gets `409`.
- **Title**: when the first message arrives, a task runs in parallel with the answer. It asks
  `title_model` for 3 to 6 words in the question's language through structured output (a
  Pydantic model with the title and its maximum length), because a plain prompt was not
  followed in the check of 2026-10-12. On failure or without a key the title is the question
  cut to `title_max_chars` (`title_source = fallback`). A title the user sets is kept. The
  model choice is open (section 15).

## 9. API and streaming

| Method and path | Purpose |
|---|---|
| `POST /chat/threads` | create a chat |
| `GET /chat/threads` | list chats, newest first |
| `PATCH /chat/threads/{id}` | rename |
| `DELETE /chat/threads/{id}` | delete |
| `GET /chat/threads/{id}/messages` | history from `chat_messages` |
| `POST /chat/threads/{id}/messages` | body `{text}`; streams the answer |
| `POST /chat/messages/{id}/feedback` | thumbs up or down, optional comment |

Pydantic models at every boundary; the existing CORS, trusted-host and `Origin` checks apply.

The answer streams as `text/event-stream` through Starlette's `StreamingResponse` with explicit
headers, in the AI SDK UI message stream protocol (header `x-vercel-ai-ui-message-stream: v1`).
FastAPI's own `EventSourceResponse` drops custom headers (checked on 2026-10-12), so it is not
used and the FastAPI pin stays.
The adapter reads `agent.astream(stream_mode=["messages", "updates"], version="v2")` (the
stable API; `astream_events` v3 is beta):

| Agent output | Stream part |
|---|---|
| turn start | `start` |
| title ready (first message only) | `data-title` |
| text tokens from the `model` node | `text-start`, `text-delta`, `text-end` |
| a `run_sql` tool call | `tool-input-available` (the SQL) |
| a tool message with its artifact | `tool-output-available` (rows, columns, truncated, error) |
| end | `finish`, then `[DONE]` |
| failure | `error` with readable text, never a traceback |

A test fixes the parts emitted for a scripted agent run, so a protocol change in AI SDK shows
up as one failing test.

**CLI**: `finance chat [QUESTION] [--thread ID]` runs the same chat service: without a
question it is interactive; it prints the streamed answer and each query; its chats appear in
the web list.

## 10. Web `/chat` (plan 4b)

- `useChat` (`@ai-sdk/react`) with a transport that sends only the new message's text to the
  chat's endpoint, since the API holds the history.
- AI Elements is not used: its components are built on Radix, while the web app's shadcn setup
  uses Base UI (`style: base-nova`); several of them (`PromptInput`, message actions, `Tool`)
  rely on Radix-only props such as `asChild`. Decided with Raul on 2026-10-12: own small
  components on the existing kit, with the two libraries AI Elements wraps: `streamdown`
  (markdown while streaming) and `use-stick-to-bottom` (auto-scroll).
- Components: the conversation, a message (markdown), the query disclosure (SQL and its rows),
  the input with send and stop, feedback buttons, and a sidebar of chats (list, new, rename,
  delete; the title arrives live).
- An entry in the navigation. Detailed layout and copy are decided in the 4b plan.

## 11. Observability

- One trace per turn: a root observation of type `agent` named `chat-turn`, input the
  question, output the final answer. Model generations (tokens including reasoning, cost),
  `run_sql` tool spans (SQL in, compact table out) and summaries nest under it through
  `langfuse.langchain.CallbackHandler` (one handler per request). The title is its own
  observation (`chat-title`) in the same session.
- Attributes set once, at the start of the turn, with `propagate_attributes`: `session_id`
  is the thread id, `user_id` is `chat.user_id`, `tags=["chat"]`, `version` is a short hash
  of `system.md`, metadata carries a hash of the semantic-layer YAML, the model and the
  reasoning effort. (Langfuse v4 drops trace metadata changed mid-run, and several clients
  disable tracing: the single client in `finance/tracing.py` is reused.)
- Deterministic scores per turn: `sql_calls`, `sql_errors` (numeric), `hit_sql_limit`,
  `stopped`, `infra_error` (boolean).
- User feedback becomes a `user-feedback` score on the answer's trace.
- A failed turn (infrastructure or model error) is marked `ERROR` on its observation, and a turn
  that reached the query limit `WARNING` (it still answered).
- Flushed on API shutdown and at the end of `finance chat`. Without keys nothing is recorded.
- Prompts stay in git, versioned by hash; Langfuse prompt management is not used.
- Setup note: Langfuse needs a model definition with `grok-4.7` prices to compute cost.

Privacy (amends v1 section 2): the LLM and Langfuse receive the questions, the SQL and query
results (merchant names, amounts, dates, notes, account names), never IBANs or raw bank
descriptions.

## 12. Settings

A nested `chat: ChatSettings` group in `finance/settings.py` (`env_nested_delimiter="__"`,
so `CHAT__MODEL=...` overrides it from `.env`). Every field has a description and bounds;
reasoning efforts are a `Literal["low", "medium", "high", "xhigh"]`.

| Field | Default |
|---|---|
| `model`, `reasoning_effort` | `xai:grok-4.7`, `high` |
| `summary_model`, `summary_reasoning_effort` | `xai:grok-4.7`, `medium` |
| `title_model` | `xai:grok-4.20-non-reasoning` |
| `max_retries` | 2 |
| `summary_trigger_tokens`, `summary_keep_messages` | 150000, 20 |
| `clear_tool_results_trigger_tokens`, `clear_tool_results_keep` | 15000, 4 |
| `max_sql_calls_per_turn`, `max_model_calls_per_turn`, `recursion_limit` | 8, 12, 120 |
| `sql_timeout_seconds`, `sql_row_limit`, `sql_rows_shown`, `sql_max_chars` | 10, 200, 50, 8000 |
| `title_max_chars` | 60 |
| `user_id` | `local` |

`.env.example` documents the `CHAT__*` overrides (commented out) and drops
`SUPABASE_DB_URL_READONLY`.

## 13. Testing

Unit (no database, no network; `uv run task test`):

- SQL guard matrix: a `DELETE` inside a CTE is rejected; a `'%drop%'` literal passes;
  `set_config`, an unknown table, a schema-qualified table and two statements are rejected.
- Result formatting and truncation; the hint for each Postgres error class.
- Semantic layer: YAML schema, kinds, the two-way column check against a fake catalog, and
  the snapshot of the rendered data context.
- Middleware: dangling tool calls closed; infrastructure stop ends the turn without a model
  call.
- The agent loop with a LangChain fake chat model that emits tool calls: limits, messages,
  artifacts.
- The AI SDK stream adapter (fixed parts for a scripted run); the chat API with a fake agent
  (create, list, rename, delete, `409` on a concurrent turn, `stopped` on disconnect);
  settings bounds; the title fallback.

Integration (local Supabase; `uv run task test-integration`):

- `agent_reader` reads `agent.transactions` and `agent.subscriptions`, and gets "permission
  denied" on `public.transactions`.
- A write sent straight to the executor (bypassing the guard) fails in the read-only
  transaction.
- Metrics and examples pass `EXPLAIN`; the YAML matches the live views.
- A checkpointer round trip and a thread deletion.

Manual: the smoke set in section 1 through `finance chat`, reviewed in Langfuse. Raul adds a
few notes on real movements first (the ledger has none yet). Nothing from these runs is
committed.

## 14. Delivery

**4a — backend.** Migration (schema, views, role, chat tables); semantic layer files, loader,
validation and data context; instructions; `run_sql`; agent and middleware; persistence,
stop and title; API, stream adapter and feedback; Langfuse; settings and `.env.example`;
`finance chat`; README (setup, how the chat works, the jev section without the router) and
`docs/backlog.md` (section 15). New dependencies: `langchain`, `langgraph`,
`langgraph-checkpoint-postgres`, `langchain-xai`, `sqlglot`.

**4b — web.** The `/chat` page in section 10, the navigation entry, an `agent-browser` core
check of the chat flows and one dogfood pass before merge.

4b starts after 4a is merged, because it consumes the generated API types.

## 15. Out of scope and open decisions

Out of scope for slice 4:

- A golden dataset and an eval harness. Until then, regressions are found by comparing traces
  across prompt and semantic-layer versions in Langfuse; traces can later be added to a
  Langfuse dataset.
- Account balances (needs the statement position of each movement stored at import).
- Writing from the chat: categories, notes, event tags (`docs/backlog.md`).
- Charts in the chat, memory across threads, financial advice.
- Authentication and several users; a second model provider as fallback; Langfuse prompt
  management.
- Row-level security on the `public` tables, which the Supabase Data API exposes today: a
  separate task, needed before any hosted deployment.

Open decisions:

- The title model (`grok-4.20-non-reasoning` is provisional).
- Reasoning efforts after real use (`high` may prove slow for the agent).

## 16. Changes to the v1 spec

| v1 section | Change |
|---|---|
| 2 Principles | the LLM and Langfuse receive query results (section 11) |
| 3.1 Database | one database URL; the agent reads schema `agent` through `SET LOCAL ROLE agent_reader`; `SUPABASE_DB_URL_READONLY` removed |
| 3.2 Schema | `semantic_schema` and `semantic_metrics` dropped; `chat_threads`, `chat_messages` and schema `agent` added |
| 8 Semantic layer | YAML in the repo plus values read from the database; the data context travels as runtime context, apart from the instructions |
| 9 Chat agent | the jev router (9.1) and `describe_schema` (9.2) are dropped; one `create_agent` loop with `grok-4.7`, middleware and the `run_sql` contract in section 7 |
| 9.3 Streaming | AI SDK UI message stream protocol (section 9) |
| 10 API | the endpoints in section 9 |
| 11 Web | `/chat` with `useChat` and own components (section 10) |
| 13 Observability | the per-turn trace, scores and feedback (section 11); the `chat` settings group (section 12) |
| 14 Slices | slice 4 is delivered as two plans (section 14) |

### Plan 4a amendments (2026-10-12)

Found while validating the plan's code against the libraries and a scratch database:

- Section 5: each query example holds its SQL as a list of steps, and every step passes the
  SQL guard and `EXPLAIN`.
- Section 5.4: the data context is about 6,000 tokens on the real taxonomy.
- Section 8: `chat_messages.feedback` stores the thumbs, so the UI shows them on reload.
- Section 9: the stream uses `StreamingResponse` with explicit headers; FastAPI's
  `EventSourceResponse` drops the AI SDK header.
- Section 10: no AI Elements (Radix) on a Base UI app; own components with `useChat`,
  `streamdown` and `use-stick-to-bottom`.
- Section 12: `recursion_limit` defaults to 120 (a query costs about 7 graph steps; 60 ended a
  turn of 8 queries before the query limit).
- Section 8: a stop over real HTTP must still save the stopped answer (the relay shields its
  wait for the turn); feedback is one Langfuse score per answer (`score_id`).

## 17. References

- LangChain agents, middleware, runtime and streaming:
  https://docs.langchain.com/oss/python/langchain/middleware/built-in,
  https://docs.langchain.com/oss/python/langchain/runtime,
  https://docs.langchain.com/oss/python/langchain/streaming
- LangGraph checkpointers: https://docs.langchain.com/oss/python/langgraph/checkpointers
- Supabase connections: https://supabase.com/docs/guides/database/connecting-to-postgres
- xAI reasoning: https://docs.x.ai/developers/model-capabilities/text/reasoning
- AI SDK stream protocol: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol
- AI Elements: https://github.com/vercel/ai-elements
- Langfuse with LangChain: https://langfuse.com/integrations/frameworks/langchain
- Anthropic, "Effective context engineering for AI agents" and "Writing effective tools for
  agents": https://www.anthropic.com/engineering

## Appendix A. Instructions draft

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
     (SELECT <column>, COUNT(*) ... WHERE <column> ILIKE '%term%' GROUP BY <column> ... LIMIT 20),
     try variants (accents, short brand name, singular), then filter with the exact values found.
     Never look up and aggregate in the same query.
   - Notes: the user's words rarely match literally. List the distinct notes (with counts and
     dates) and choose by meaning.
   Lookups for different filters can run in parallel; the final query runs after them.
4. Write one query that answers the question. Totals, shares, averages and deltas are computed in
   SQL, never in your head. When listing movements, include the note.
5. Check before running: every column exists in that model, every filter is resolved, measures
   are aggregated in totals and never grouped, the period is explicit, listings have a LIMIT.
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
  measure (aggregate it in totals, show it as it is when listing movements; never group by it),
  dimension (group or filter; with allowed values use them as they are, without them look up
  first), time (filter and group periods), text (search it and read it; group by it only to list
  its distinct values, never as the breakdown of an answer), flag (true or false filter).
- Metrics: use their definitions exactly.
- Query examples: patterns to adapt, not templates to copy.
```

## Appendix B. Semantic layer

The validated files are in plan 4a (Task 5); `transactions.yaml` as built:

`transactions.yaml`:

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
        meaning: money in (amount >= 0)
      - value: outgoing
        meaning: money out (amount < 0)
  - attribute: tx_type
    kind: dimension
    description: >
      What the movement counts as. It follows the category; a movement without a category follows
      its sign.
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
      the user means. Do not total by it, because one business has many spellings.
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

`subscriptions.yaml` follows the same shape: one row per merchant with at least one money-out
charge flagged as a subscription; `merchant` (same names as in transactions), `charges`,
`last_charge`, `typical_amount` (median charge), `cadence` (`monthly`, `yearly`: yearly when
the median gap between charges is over 200 days), `monthly_equivalent` (summed over active
rows it is the monthly cost of subscriptions), `active` (charged within 45 days for monthly or
400 days for yearly of the latest imported movement, not of today). Not for single charges or
spending totals (use transactions with `is_subscription`), and subscriptions paid by credit
card are not itemized.

Rendered values in the data context look like:

```
- groceries (shopping, expense): supermarkets, grocery stores, bakeries, butchers, fruit shops, food markets
- 'BBVA ····0001' (bbva): statements from 2025-01-01 to 2025-12-31
```
