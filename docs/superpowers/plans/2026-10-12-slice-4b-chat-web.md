# Slice 4b — The Chat Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `/chat` page where the user asks questions about their own bank data, watches the answer stream with the queries behind it, stops it, keeps every chat (list, reopen, rename, delete) and rates answers, on top of the plan 4a API.

**Architecture:** `useChat` (`@ai-sdk/react`) talks to the 4a API straight from the browser through one `DefaultChatTransport`, whose `prepareSendMessagesRequest` points each chat at `POST /chat/threads/{id}/messages` and sends only `{text}` (the API keeps the history). A client provider in the `/chat` layout owns the sidebar's thread list and one AI SDK `Chat` per opened thread, so an answer keeps streaming across navigations: a new chat starts on `/chat` and moves to `/chat/<id>` after its first question. Server components fetch the thread list and a chat's history; answers render as markdown with `streamdown`, the conversation follows the stream with `use-stick-to-bottom`, and everything else is a small component on the existing Base UI kit. Pure helpers in `src/lib` map the API's history to UI messages and hold the rules the components share.

**Tech Stack:** Next.js 16.3.6 App Router, React 19.2.8, TypeScript, Tailwind v4, shadcn `base-nova` (Base UI), AI SDK 7 (`ai` 7.0.137, `@ai-sdk/react` 4.0.140), `streamdown` 2.7.0, `use-stick-to-bottom` 1.1.6, Vitest for `src/lib`, `agent-browser` for the UI; one Python test tool in `apps/api/tests` for the browser checks.

**Spec:** `docs/superpowers/specs/2026-10-12-slice-4-chat-design.md`, sections 8, 9, 10, 11, 14 and the "Plan 4a amendments" in section 16. The API contract is plan 4a (`docs/superpowers/plans/2026-10-12-slice-4a-chat-backend.md`): Task 4 (`QueryResult`, `Thread`, `ChatMessage`), Task 9 (the stream parts), Task 11 (`stream_turn`: `start.messageId` is the saved answer's id, `data-title` only on a chat's first turn, `error` with `ERROR_TEXT`, one turn at a time), Task 12 (the routes, 404, 409, 503) and Task 14 (the generated `apps/web/src/lib/api-types.ts`). Where plan 4a's code blocks and the shipped code differ, the shipped code and the regenerated types are the contract.

**How this plan was validated:** on 2026-10-12, in a sandbox copy of the repo with plan 4a implemented and its tests passing, against a throwaway Postgres 17 holding the migrations, the seed and a synthetic month in 1999:

- The 4a stream of seven scripted scenarios (an answer with a query, text only, a model failure, a failed query, 500 rows, two queries, the query limit), captured with curl, was parsed with `ai@7.0.137`'s own `parseJsonEventStream` and `uiMessageChunkSchema` (every part valid) and turned into messages with `readUIMessageStream`. The shapes are in "The stream as useChat sees it".
- Every file below was written in a copy of `apps/web` and checked at the state each task leaves it in: `npm run lint`, `npx tsc --noEmit`, `npm test` (89 tests: 72 existing and 17 new; 18 new after the isRefused amendment) and `npm run build` all green. `apps/api/tests/scripted_chat_server.py` passes `ruff check` and `ruff format --check`.
- The flows were run with `agent-browser` against the 4a API on scripted models (the server of Task 2), in `next dev` (React's development double rendering included): a new chat from an example and from the box, the answer streaming across the move to `/chat/<id>` with the title arriving mid-answer, the query disclosure (two queries, a failed query, 500 rows cut at 200), Stop, a stream error, a 409 from a second turn, reload, leaving a chat mid-answer and coming back, rename (focus back on Rename), delete, thumbs up and thumbs down with a comment (stored, shown after reload), the 503 state, the API stopped, a 480 px tall window and a 390 px phone with the chats sheet.
- Two 4a defects were found and reproduced (P1, P2 below); both are now fixed in plan 4a, with tests.

No paid model call was made and the real local database (port 54322) was not touched. Copy the code as written; if a library behaves differently, stop and report instead of improvising.

## The stream as useChat sees it

Validated with `ai` 7.0.137 on the 4a stream:

| 4a part | What useChat builds |
|---|---|
| `start` `{messageId}` | an assistant message with that id (the id `POST /chat/messages/{id}/feedback` takes) |
| `tool-input-available` (`toolName: "run_sql"`) | a part `{ type: "tool-run_sql", toolCallId, state: "input-available", input: { sql } }` (a static tool: no `dynamic` flag, so the type is `tool-<name>`) |
| `tool-output-available` | the same part with `state: "output-available"` and `output`: the `QueryResult` (`sql, columns, rows, row_count, truncated, duration_ms, error, hint, infra_error`), or `{error}` alone when the query limit refused the call |
| `text-start/delta/end` (`text-0`, `text-1`…) | one `{ type: "text", text, state: "streaming" \| "done" }` part per text id, in order with the tool parts |
| `data-title` `{data: {threadId, title}, transient: true}` | the `onData` callback only (Task 0 adds `transient`; before it, the part also landed in the answer's parts, which `answerBlocks` skips anyway) |
| `error` `{errorText}` | useChat stops reading: `status` `"error"`, `error.message` = the API's `ERROR_TEXT`; the parts before it stay; `finish` and `[DONE]` are not read |
| an HTTP refusal before the stream (404, 409, 422, 503) | an `APICallError` with `statusCode` and `responseBody` (FastAPI's JSON); the question stays in `messages`, with no answer |

`DefaultChatTransport` parses the body and never reads the `x-vercel-ai-ui-message-stream` header, so CORS needs no `expose_headers`.

## Plan 4a defects found while validating

Found while validating this plan against 4a's API in a browser, and fixed in plan 4a on 2026-10-12 before handoff (each pinned by a 4a test):

- **P1, fixed.** Stop over real HTTP lost the stopped answer: the server's cancellation reached the turn inside its save. 4a's `ChatService._relay` now shields its wait (Task 11), and Task 12 has a test that closes a real HTTP stream mid-answer. Tasks 3 to 6 here rely on it.
- **P2, fixed.** `recursion_limit` defaults to 120 (it was 60, which ended a turn of 8 sequential queries with an error); 4a Task 8 tests that the query limit is reached first.
- **P3, known limitation.** When the first turn is stopped before its title arrives, the title is stored but its `data-title` goes to a closed stream: the sidebar shows "Untitled chat" until a reload.
- **P4, fixed.** Feedback sends `score_id=f"{message_id}-feedback"`, so a new click replaces the answer's score in Langfuse.

## Decisions in this plan (confirm with Raul)

- **A. Rename and Delete act on the open chat, from its title row.** Spec 10 lists them under the sidebar; per-item menus need a dropdown with focus handling, while the title row has room for both and shows the live title. The sidebar items are plain links.
- **B. Feedback.** Thumbs up is sent at once; thumbs down opens an optional "What was wrong?" field and sends one request with both. Thumbs appear only on answers that ended `ok` (a stopped or failed answer shows a note instead). The pressed thumb can change; it cannot be cleared (the API takes only `up` or `down`).
- **C. Empty state.** Four generic example questions start a chat in one click; they carry no personal data.
- **D. A scripted chat server is committed** at `apps/api/tests/scripted_chat_server.py` (Task 2): every chat check runs on it (recipe R3) without model spend, now and in later slices. It refuses any database not named `scratch_*`.
- **E. Navigation.** "Chat" sits between Subscriptions and Review. A thread without a title reads "Untitled chat", never "New chat", which names the button.
- **F. Conflict to settle: shadcn's chat components.** `.claude/skills/shadcn/rules/chat.md` (installed with the shadcn skill) asks for shadcn's `message-scroller`, `message`, `bubble` and `marker`, which now exist for `base` too (`npx shadcn@latest add message-scroller message bubble marker --dry-run` lists them; they depend on `@shadcn/react` 0.3.1 and would overwrite the local `button.tsx`), and says not to use a stick-to-bottom hook. Spec 10, decided on 2026-10-12, chose `use-stick-to-bottom` and own components. This plan follows spec 10; switching later touches only `conversation.tsx` and `chat-message.tsx`.

### Decided with Raul on 2026-10-12

A to F as written. On the carry-overs from the 4a reviews:

- **CORS:** no `expose_headers` (checked in `ai` 7.0.137: the transport never reads the header).
- **`data-title` is transient:** the API sends it with `"transient": true`, so useChat passes it to `onData` only and it never enters an answer's parts (Task 0; checked in `ai` 7.0.137's `processUIMessageStream`).
- **Limit copy:** the model-call limit notice reaches the user as `LIMIT_MESSAGE` (Task 0), not LangChain's text; a query the per-turn limit refused (`{error}` without `rows`) reads "Not run: this answer had already used its query limit." and counts as "not run", not "failed" (Tasks 1 and 3).
- **Rename keeps the chat's place:** the list is ordered by activity; renaming does not touch `updated_at` (Task 0) and the provider patches the title in place (Task 3).
- **Backlog 8:** nothing extra in the UI; the query disclosure is the visibility.

## Global Constraints

- Everything in English: code, comments, docs, commits, UI copy (sentence case).
- Simplicity is a requirement: one responsibility per file, no abstraction for a single caller, 15 readable lines over 30 clever ones. Do not reuse code, prompts or domain logic from Raul's former employer's repos (Simon).
- 4b starts after 4a is merged. Web types come from `npm run gen:api` (API on :8000) into `apps/web/src/lib/api-types.ts`; code uses `Schemas["Thread"]`, `Schemas["ChatMessage"]` and `Schemas["QueryResult"]` through the aliases in `@/lib/chat`.
- This is Next.js 16.3.6, not the Next.js of training data. Read the guide in `apps/web/node_modules/next/dist/docs/` before using an API (`apps/web/AGENTS.md`): `01-app/03-api-reference/03-file-conventions/layout.md`, `dynamic-routes.md`, `not-found.md`, `route-segment-config` and `01-app/01-getting-started/04-linking-and-navigating.md`. `params` is a Promise; `PageProps<"/route">` and `LayoutProps<"/route">` are global types generated by `next typegen`, `next dev` or `next build`. A page or layout that fetches exports `export const dynamic = "force-dynamic"`, so `next build` never calls the API.
- shadcn `base-nova` runs on Base UI, not Radix: `render={<Button />}`, never `asChild`; a link styled as a button is a Next `<Link>` with `className={buttonVariants(...)}`; icons from `lucide-react` with `data-icon` inside buttons; `cn` from `@/lib/utils`. Follow `.claude/skills/shadcn/rules/*.md`, except `chat.md` (Decision F). No new shadcn component is needed.
- The AI SDK packages are pinned exactly (`--save-exact`): the 4a stream was validated against `ai` 7.0.137 and `@ai-sdk/react` 4.0.140, which must move together. Upgrade them on purpose, in their own change, after re-running the stream check. `zod` arrives as `ai`'s peer; do not add it.
- The transport sends only the new question's text (spec 10). The browser calls the API directly at `NEXT_PUBLIC_API_URL` (`localhost`, port 8000; 8001 in R3): the API's CORS, trusted-host and `Origin` checks apply.
- Visual system as in slice 3 (`globals.css`): white page, `bg-card` surfaces without borders, muted text `#6b6b75`, one accent, errors in `text-bad`, Geist with tabular numbers, light mode only. The user's question is a `bg-card` bubble on the right; an answer is plain text on the left.
- Accessibility as in 3b: every control has a name, focus stays visible and never drops to the page after an action, contrast follows Decision B of plan 3b, the conversation is a `role="log"` region, errors are `role="alert"`, and nothing scrolls sideways at 390 px.
- Testing policy: pure helpers in `src/lib` get Vitest tests (they run with `TZ=America/Los_Angeles`, as configured); components are checked in the browser with `agent-browser`, not with unit tests. CI stays lint, type-check and build. The local gate for every web task is `cd apps/web && npm run lint && npx next typegen && npx tsc --noEmit && npm test && npm run build` (`next typegen` first: a new route's `PageProps` type does not exist before it).
- No paid model calls: every chat check runs on the scripted server (R3). The only paid calls are Task 7 Step 6, with Raul's explicit approval. **Never run `supabase db reset`.** Never point the scripted server at the real database (it refuses names other than `scratch_*`).
- The repo is public: no real amounts, merchants, account digits or statement names in code, tests, docs, commit messages or PR text. Screenshots go only to `dogfood-output/slice-4b/` (git-ignored: they show real data), by absolute path.
- Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`), no attribution trailer. Push with the command in `CLAUDE.md`.

## Review Focus

The inputs and conditions most likely to bite a person using the chat, each pinned by a check in the task that owns the code:

1. **Stopping an answer, or closing the tab mid-answer.** The partial answer is saved as `stopped`, the page says "You stopped this answer." live and after a reload, and the next question in that chat is answered. Checks: Task 1 `toUIMessages` "drops the text part of an answer stopped before any text"; Task 4 browser check, Step 5 ("Stop"); Task 3 check of a chat stopped through curl. Needs P1.
2. **A question the API refuses or never gets** (a 409 while another tab's answer runs, the API stopped). The question is not lost and not shown as sent: it goes back into the box with the reason. Checks: Task 1 `unanswered` and `chatErrorText`; Task 4 browser check, Step 7 ("409").
3. **Leaving a chat while it answers** (a new chat moving from `/chat` to `/chat/<id>`, or opening another chat and coming back). The answer keeps streaming and Stop still works. Checks: Task 4 browser check, Step 8; Task 5 browser check, Steps 3 and 5.
4. **Opening "Ran N queries" while the view follows the bottom.** The queries stay where the user clicked instead of being scrolled out of view. Check: Task 3 browser check, Step 3 (the summary's position before and after opening).
5. **An unusual history:** a failed query, a 500-row result, a failed answer, a stopped answer without text, a 120-character unbroken string on a phone. Each renders readably, with no sideways scroll. Checks: Task 1 `rowsLabel`, `toUIMessages`, `answerBlocks`; Task 3 browser check, Steps 4 to 7; Task 4 browser check, Step 9.

## Browser checks

Every task that changes the web ends with a check that follows one of these recipes. Load the workflow once per session with `agent-browser skills get core`. The shell does not keep variables or functions between commands, so each command below is self-contained; write the ids it prints into the next commands by hand.

### R1 — real data, read-only

As in plan 3b: the API (`cd apps/api && uv run task api`, :8000) and the web (`cd apps/web && npm run dev`, :3000) on the real local database; session `slice4b`; only `http://localhost:3000`; navigate and read, never send a chat question (it would call xAI), rename, delete or rate.

### R3 — the chat on scripted models (scratch database)

1. Copy the local database into `scratch_review`, with the `agent` schema and its grants (unlike R2, privileges are kept: `agent_reader` needs its grants on the `agent` views):

```bash
PGPASSWORD=postgres dropdb --if-exists -h 127.0.0.1 -p 54322 -U postgres scratch_review
PGPASSWORD=postgres createdb -h 127.0.0.1 -p 54322 -U postgres scratch_review
docker exec supabase_db_personal-finance-agent pg_dump -U postgres --schema=public --schema=agent --no-owner postgres | PGPASSWORD=postgres psql -q -h 127.0.0.1 -p 54322 -U postgres scratch_review
PGPASSWORD=postgres psql -h 127.0.0.1 -p 54322 -U postgres scratch_review -tAc "select has_table_privilege('agent_reader', 'agent.transactions', 'select')"
```

Expected: `t`. The errors `schema "public" already exists` and `permission denied to change default privileges` are expected.

2. Start the scripted API on :8001, as a background process:

```bash
cd apps/api && CORS_ORIGINS='["http://localhost:3001"]' uv run python -m tests.scripted_chat_server --port 8001 --db-url postgresql://postgres:postgres@127.0.0.1:54322/scratch_review
```

3. Build and start the web on :3001 against it, as a background process (Next 16 refuses a second `next dev` in one folder):

```bash
cd apps/web && NEXT_PUBLIC_API_URL=http://localhost:8001 npx next build && NEXT_PUBLIC_API_URL=http://localhost:8001 npx next start -p 3001
```

4. Use the session `slice4b-scratch` and only `http://localhost:3001`. The scripted agent answers from words in the question (Task 2): `hello`, `slow`, `fail`, `error`, `big`, `two`, anything else. Titles arrive 1.5 s after the question.
5. Afterwards, stop both processes and drop the copy: `PGPASSWORD=postgres dropdb -h 127.0.0.1 -p 54322 -U postgres scratch_review`.

## File Structure

| File | Responsibility |
|---|---|
| `apps/web/package.json`, `package-lock.json` | `ai`, `@ai-sdk/react`, `streamdown`, `use-stick-to-bottom`, pinned |
| `apps/web/src/app/globals.css` | Tailwind scans Streamdown's classes |
| `apps/web/src/lib/api.ts` | failed GETs throw `ApiError` (status, detail); `apiPost<T>` returns its JSON |
| `apps/web/src/lib/chat.ts` (new) | chat types; history → UI messages; request body; answer blocks; thinking; rows label; error text |
| `apps/web/src/lib/chat-threads.ts` (new) | the sidebar's list: title fallback, order, patch, drop |
| `apps/web/src/lib/chat-api.ts` (new) | the chat routes and useChat's transport |
| `apps/api/tests/scripted_chat_server.py` (new) | the API with scripted models for browser checks (R3) |
| `apps/web/src/app/layout.tsx` | the chat fills the window below the top bar |
| `apps/web/src/app/chat/layout.tsx` (new) | thread list from the API, sidebar, "not set up" state |
| `apps/web/src/app/chat/page.tsx` (new) | `/chat`: a new chat |
| `apps/web/src/app/chat/[id]/page.tsx` (new) | `/chat/<id>`: a saved chat, 404 when unknown |
| `apps/web/src/components/chat/chats-provider.tsx` (new) | threads state and one AI SDK `Chat` per thread |
| `apps/web/src/components/chat/thread-list.tsx` (new) | New chat and the saved chats |
| `apps/web/src/components/chat/chat-header.tsx` (new) | the title row; the chats sheet on phones |
| `apps/web/src/components/chat/thread-header.tsx` (new) | the open chat's title, Rename, Delete |
| `apps/web/src/components/chat/conversation.tsx` (new) | useChat, the message log, errors, the box |
| `apps/web/src/components/chat/chat-message.tsx` (new) | a question bubble or a markdown answer |
| `apps/web/src/components/chat/query-disclosure.tsx` (new) | an answer's queries: SQL, rows, errors |
| `apps/web/src/components/chat/composer.tsx` (new) | the question box with Send and Stop |
| `apps/web/src/components/chat/new-chat.tsx` (new) | the empty state, examples, the first question |
| `apps/web/src/components/chat/feedback-buttons.tsx` (new) | thumbs with an optional comment |
| `apps/web/src/components/shell/nav-links.tsx` | the "Chat" entry |
| `CLAUDE.md`, `README.md` | the new pages, recipe R3, status (Task 7) |

---

## Before Task 1

- [ ] **Step 1: Branch from main after 4a is merged**

```bash
git switch main && git pull
git switch -c feat/slice-4b-chat-web
```

P1 is fixed in plan 4a (Tasks 11-12): confirm 4a's `test_a_request_closed_mid_answer_saves_the_stopped_answer_over_real_http` passes before starting. If it does not, stop and ask.

- [ ] **Step 2: Check the web types carry the chat**

```bash
cd apps/web && grep -cE '^        (Thread|ChatMessage|QueryResult): \{' src/lib/api-types.ts
```

Expected: `3`. If not, start the API (`cd apps/api && uv run task api`), run `npm run gen:api`, and commit `src/lib/api-types.ts` alone (`chore: regenerate the web API types`).

- [ ] **Step 3: Check the starting point**

Run: `cd apps/web && npm run lint && npx next typegen && npx tsc --noEmit && npm test && npm run build`
Expected: no errors; 72 tests pass.

---

### Task 0: Backend carry-overs from the 4a reviews

**Files:**
- Modify: `apps/api/finance/agent/service.py`, `apps/api/finance/agent/ui_stream.py`, `apps/api/finance/agent/middleware.py`, `apps/api/finance/agent/store.py`
- Test: `apps/api/tests/test_ui_stream.py`, `apps/api/tests/test_chat_api.py`

**Interfaces:**
- Produces: `data-title` parts carry `"transient": True`; `finance.agent.middleware.LIMIT_MESSAGE`; `PATCH /chat/threads/{id}` leaves `updated_at` unchanged.

- [ ] **Step 1: Write the failing tests**

In `apps/api/tests/test_ui_stream.py`, `test_the_model_call_limit_notice_reaches_the_user`: import `LIMIT_MESSAGE` from `finance.agent.middleware` and replace `assert record.texts[-1].startswith("Model call limits exceeded")` with:

```python
    assert record.texts[-1] == LIMIT_MESSAGE
    deltas = [p["delta"] for p in parts if p["type"] == "text-delta"]
    assert deltas[-1] == LIMIT_MESSAGE
```

In `apps/api/tests/test_chat_api.py`, the `data-title` part the first-turn test expects becomes:

```python
    assert {
        "type": "data-title",
        "data": {"threadId": thread["id"], "title": "Movement count"},
        "transient": True,
    } in events
```

and `test_threads_can_be_renamed_and_deleted_and_unknown_ones_are_404` returns the created `thread` too and asserts `renamed["updated_at"] == thread["updated_at"]` (renaming is not activity: the list keeps its order).

Run: `cd apps/api && uv run pytest tests/test_ui_stream.py -q && uv run pytest -m integration tests/test_chat_api.py -q`
Expected: the three changed assertions fail.

- [ ] **Step 2: Make them pass**

In `apps/api/finance/agent/middleware.py`, next to `INFRA_MESSAGE`:

```python
# What the user reads when ModelCallLimitMiddleware ends a turn (its own text names the limit).
LIMIT_MESSAGE = (
    "I stopped before finishing: this question needed more steps than one answer allows. "
    "Try a narrower question."
)
```

In `apps/api/finance/agent/ui_stream.py`, the text of a chunk from the node `"ModelCallLimitMiddleware.before_model"` is `LIMIT_MESSAGE` instead of `chunk.text` (both in what is streamed and in `record.texts`, so the saved answer and `finance chat` read the same sentence). The checkpoint keeps LangChain's message: the model may read it on the next turn.

In `apps/api/finance/agent/service.py`, `_title` puts `{"type": "data-title", "data": {...}, "transient": True}` on the queue (AI SDK: a transient data part reaches `onData` only, never the message's parts).

In `apps/api/finance/agent/store.py`, `rename_thread` sets only `title` and `title_source` (drop `, updated_at = now()`).

Run the commands of Step 1, then `cd apps/api && uv run task lint && uv run task test && uv run task test-integration`.
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add apps/api/finance/agent apps/api/tests/test_ui_stream.py apps/api/tests/test_chat_api.py
git commit -m "fix: readable limit notice, transient chat title, rename keeps the chat's place"
```

---

### Task 1: Chat dependencies and the chat model in `src/lib`

**Files:**
- Modify: `apps/web/package.json`, `apps/web/package-lock.json` (through npm)
- Modify: `apps/web/src/app/globals.css`, `apps/web/src/lib/api.ts`
- Create: `apps/web/src/lib/chat.ts`, `apps/web/src/lib/chat-threads.ts`, `apps/web/src/lib/chat-api.ts`
- Test: `apps/web/src/lib/chat.test.ts`, `apps/web/src/lib/chat-threads.test.ts`

**Interfaces:**
- Consumes: `Schemas` from `@/lib/api` (`Thread`, `ChatMessage`, `QueryResult`), `API_URL`, `apiGet`, `apiPatch`, `apiDelete`.
- Produces:
  - `@/lib/api`: `apiGet` throws `ApiError(status, detail, message)` (it threw a plain `Error`; `ApiError` extends `Error` with the same message, so existing callers are unchanged); `apiPost<T = void>(path, body?, init?) → Promise<T>`.
  - `@/lib/chat`: types `Thread`, `ChatMessage`, `QueryResult`, `AnswerMeta = { status, feedback }`, `QueryOutput = QueryResult | { error: string }`, `ChatUIMessage` (`UIMessage<AnswerMeta, { title: { threadId, title } }, { run_sql: { input: { sql }, output: QueryOutput } }>`), `ChatPart`, `QueryPart` (the `tool-run_sql` part), `Block`; functions `toUIMessages(history: ChatMessage[]): ChatUIMessage[]`, `newMessageBody(messages): { text: string }` (throws unless the last message is the user's), `unanswered(messages): string | null`, `answerBlocks(parts): Block[]`, `isThinking(messages): boolean`, `rowsLabel(result: QueryResult): string`, `isRefused(output: QueryOutput): output is { error: string }`, `chatErrorText(error: Error): string`.
  - `@/lib/chat-threads`: `threadTitle(thread)`, `putFirst(threads, thread)`, `patchThread(threads, id, patch)`, `moveFirst(threads, id)`, `dropThread(threads, id)`.
  - `@/lib/chat-api`: `listThreads()`, `listMessages(threadId)`, `createThread()`, `renameThread(threadId, title)`, `deleteThread(threadId)`, `sendFeedback(messageId, value, comment?)`, `chatTransport` (a `DefaultChatTransport<ChatUIMessage>`).

- [ ] **Step 1: Add the dependencies**

Run: `cd apps/web && npm install --save-exact ai@7.0.137 @ai-sdk/react@4.0.140 streamdown@2.7.0 use-stick-to-bottom@1.1.6`
Expected: `package.json` lists `"ai": "7.0.137"`, `"@ai-sdk/react": "4.0.140"`, `"streamdown": "2.7.0"` and `"use-stick-to-bottom": "1.1.6"` under `dependencies`; `npm ls ai` shows one `ai@7.0.137`, deduped under `@ai-sdk/react`. npm may warn that `fsevents` and `unrs-resolver` have install scripts; that is unrelated.

- [ ] **Step 2: Let Tailwind see Streamdown's classes**

Streamdown styles its output with Tailwind classes, which Tailwind 4 only generates for files it scans (Streamdown's docs, "Tailwind v4"). The path is relative to `globals.css`. In `apps/web/src/app/globals.css`, after the line `@import "shadcn/tailwind.css";`, add:

```css
/* Streamdown styles the chat's answers with Tailwind classes: scan its build (path from this file). */
@source "../../node_modules/streamdown/dist/*.js";
```

- [ ] **Step 3: Write the failing tests**

Create `apps/web/src/lib/chat.test.ts`:

```ts
import { APICallError } from "ai";
import { describe, expect, it } from "vitest";

import { ApiError } from "./api";

import {
  answerBlocks,
  chatErrorText,
  isRefused,
  isThinking,
  newMessageBody,
  rowsLabel,
  toUIMessages,
  unanswered,
  type ChatMessage,
  type ChatPart,
  type ChatUIMessage,
  type QueryResult,
} from "./chat";

const query = (over: Partial<QueryResult> = {}): QueryResult => ({
  sql: "SELECT 1 AS n",
  columns: ["n"],
  rows: [["1"]],
  row_count: 1,
  truncated: false,
  duration_ms: 3,
  error: null,
  hint: null,
  infra_error: false,
  ...over,
});

const saved = (over: Partial<ChatMessage>): ChatMessage => ({
  id: "00000000-0000-4000-8000-000000000001",
  thread_id: "00000000-0000-4000-8000-0000000000aa",
  role: "assistant",
  content: "There is one.",
  queries: [],
  status: "ok",
  feedback: null,
  created_at: "1999-01-31T10:00:00Z",
  ...over,
});

const user = (text: string, id = "u1"): ChatUIMessage => ({ id, role: "user", parts: [{ type: "text", text }] });

const running = (sql: string, id: string): ChatPart => ({
  type: "tool-run_sql",
  toolCallId: id,
  state: "input-available",
  input: { sql },
});

const ran = (sql: string, id: string): ChatPart => ({
  type: "tool-run_sql",
  toolCallId: id,
  state: "output-available",
  input: { sql },
  output: query({ sql }),
});

describe("toUIMessages", () => {
  it("puts an answer's queries before its text and keeps how it ended", () => {
    const [question, answer] = toUIMessages([
      saved({ id: "q", role: "user", content: "How many?", status: "ok" }),
      saved({ queries: [query(), query({ sql: "SELECT 2" })], feedback: "up" }),
    ]);
    expect(question).toEqual({ id: "q", role: "user", metadata: undefined, parts: [{ type: "text", text: "How many?", state: "done" }] });
    expect(answer.parts.map((part) => part.type)).toEqual(["tool-run_sql", "tool-run_sql", "text"]);
    expect(answer.parts[1]).toMatchObject({ state: "output-available", input: { sql: "SELECT 2" } });
    expect(answer.metadata).toEqual({ status: "ok", feedback: "up" });
  });

  it("drops the text part of an answer stopped before any text", () => {
    const [answer] = toUIMessages([saved({ content: "", status: "stopped", queries: [query()] })]);
    expect(answer.parts.map((part) => part.type)).toEqual(["tool-run_sql"]);
    expect(answer.metadata?.status).toBe("stopped");
  });
});

describe("newMessageBody", () => {
  it("sends only the newest question's text", () => {
    expect(newMessageBody([user("first", "a"), user("¿Cuánto gasté en enero?", "b")])).toEqual({
      text: "¿Cuánto gasté en enero?",
    });
  });

  it("refuses to resend when the last message is an answer", () => {
    expect(() => newMessageBody([{ id: "a", role: "assistant", parts: [] }])).toThrow("Only a new question");
  });
});

describe("unanswered", () => {
  it("returns the question when no answer started, and null once one did", () => {
    expect(unanswered([user("Is it saved?")])).toBe("Is it saved?");
    expect(unanswered([user("Is it saved?"), { id: "a", role: "assistant", parts: [] }])).toBeNull();
  });
});

describe("answerBlocks", () => {
  it("joins consecutive queries, keeps text where it streamed and hides the title part", () => {
    const blocks = answerBlocks([
      { type: "text", text: "Let me check.", state: "done" },
      ran("SELECT 1", "c1"),
      ran("SELECT 2", "c2"),
      { type: "data-title", data: { threadId: "t", title: "Counting" } },
      { type: "text", text: "Two.", state: "streaming" },
    ]);
    expect(blocks.map((block) => block.kind)).toEqual(["text", "queries", "text"]);
    expect(blocks[1].kind === "queries" && blocks[1].queries.map((q) => q.toolCallId)).toEqual(["c1", "c2"]);
    expect(blocks[2]).toEqual({ kind: "text", text: "Two.", streaming: true });
  });

  it("skips empty text parts", () => {
    expect(answerBlocks([{ type: "text", text: "", state: "streaming" }])).toEqual([]);
  });
});

describe("isThinking", () => {
  const answer = (...parts: ChatPart[]): ChatUIMessage => ({ id: "a", role: "assistant", parts });

  it("is true until something moves on screen", () => {
    expect(isThinking([user("q")])).toBe(true);
    expect(isThinking([user("q"), answer()])).toBe(true);
    expect(isThinking([user("q"), answer(ran("SELECT 1", "c1"))])).toBe(true);
  });

  it("is false while a query runs or text streams", () => {
    expect(isThinking([user("q"), answer(running("SELECT 1", "c1"))])).toBe(false);
    expect(isThinking([user("q"), answer(ran("SELECT 1", "c1"), { type: "text", text: "One", state: "streaming" })])).toBe(false);
  });
});

describe("rowsLabel", () => {
  it("counts rows and says when the result was cut", () => {
    expect(rowsLabel(query({ row_count: 0, rows: [] }))).toBe("No rows");
    expect(rowsLabel(query())).toBe("1 row");
    expect(rowsLabel(query({ row_count: 8 }))).toBe("8 rows");
    expect(rowsLabel(query({ row_count: 200, truncated: true }))).toBe("First 200 rows (there were more)");
  });
});

describe("isRefused", () => {
  it("tells a query the limit refused from one that ran or failed", () => {
    expect(isRefused({ error: "Tool call limit exceeded." })).toBe(true);
    expect(isRefused(query({ error: "column x does not exist" }))).toBe(false);
    expect(isRefused(query())).toBe(false);
  });
});

describe("chatErrorText", () => {
  const refused = (statusCode: number, responseBody: string) =>
    new APICallError({ message: responseBody, url: "http://localhost:8000/chat", requestBodyValues: {}, statusCode, responseBody });

  it("passes the API's own sentences through", () => {
    expect(chatErrorText(refused(409, '{"detail":"This chat is still answering. Wait for it or stop it first."}'))).toBe(
      "This chat is still answering. Wait for it or stop it first.",
    );
    expect(chatErrorText(new Error("Something went wrong while answering. Try again."))).toBe(
      "Something went wrong while answering. Try again.",
    );
  });

  it("explains a missing chat, a chat that is not set up and an unreachable API", () => {
    expect(chatErrorText(refused(404, '{"detail":"chat x not found"}'))).toBe("This chat no longer exists. Start a new one.");
    expect(chatErrorText(refused(503, "{}"))).toContain("XAI_API_KEY");
    expect(chatErrorText(new TypeError("Failed to fetch"))).toContain("Could not reach the API");
    expect(chatErrorText(refused(409, "not json"))).toBe("This chat is still answering. Wait for it or stop it first.");
  });

  it("reads the chat routes' own errors too", () => {
    expect(chatErrorText(new ApiError(404, "chat x not found", "GET failed"))).toBe("This chat no longer exists. Start a new one.");
    expect(chatErrorText(new ApiError(500, null, "POST /chat/threads failed with 500"))).toBe("The API refused the request (500).");
  });
});
```

Create `apps/web/src/lib/chat-threads.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { Thread } from "./chat";
import { dropThread, moveFirst, patchThread, putFirst, threadTitle } from "./chat-threads";

const thread = (id: string, title: string | null = null): Thread => ({
  id,
  title,
  title_source: title ? "model" : null,
  created_at: "1999-01-31T10:00:00Z",
  updated_at: "1999-01-31T10:00:00Z",
});

describe("thread list", () => {
  const list = [thread("a", "Groceries"), thread("b"), thread("c", "Trips")];

  it("names a thread that has no title yet", () => {
    expect([threadTitle(list[0]), threadTitle(list[1])]).toEqual(["Groceries", "Untitled chat"]);
  });

  it("puts a new thread first, once", () => {
    expect(putFirst(list, thread("d")).map((t) => t.id)).toEqual(["d", "a", "b", "c"]);
    expect(putFirst(list, thread("c", "Holidays")).map((t) => [t.id, t.title])).toEqual([
      ["c", "Holidays"],
      ["a", "Groceries"],
      ["b", null],
    ]);
  });

  it("moves a thread that just answered to the top and ignores unknown ids", () => {
    expect(moveFirst(list, "b").map((t) => t.id)).toEqual(["b", "a", "c"]);
    expect(moveFirst(list, "zz")).toBe(list);
  });

  it("patches a title in place and drops a deleted thread", () => {
    expect(patchThread(list, "b", { title: "Rent" }).map((t) => t.title)).toEqual(["Groceries", "Rent", "Trips"]);
    expect(dropThread(list, "a").map((t) => t.id)).toEqual(["b", "c"]);
  });
});
```

- [ ] **Step 4: Run them to see them fail**

Run: `cd apps/web && npx vitest run src/lib/chat.test.ts src/lib/chat-threads.test.ts`
Expected: FAIL (`Failed to resolve import "./chat"`).

- [ ] **Step 5: Make failed GETs carry their status, and POST return its JSON**

The chat layout must tell a 503 (chat not set up) from any other failure, and creating a thread returns the new `Thread`. In `apps/web/src/lib/api.ts`:

Replace

```ts
  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

/** A failed write: the HTTP status, and FastAPI's `detail` when it is a sentence (for example
 * the 422 for an income category on money going out). */
export class ApiError extends Error {
```

with

```ts
  if (!response.ok) {
    throw await apiError(response, `GET ${path} failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

/** A failed request: the HTTP status, and FastAPI's `detail` when it is a sentence (for example
 * the 422 for an income category on money going out, or the chat's 503 when it is not set up). */
export class ApiError extends Error {
```

After the closing `}` of the `ApiError` class, add:

```ts

async function apiError(response: Response, message: string): Promise<ApiError> {
  const detail = await response.json().then(
    (json: { detail?: unknown }) => (typeof json.detail === "string" ? json.detail : null),
    () => null,
  );
  return new ApiError(response.status, detail, message);
}
```

In `send`, replace

```ts
  if (!response.ok) {
    const detail = await response.json().then(
      (json: { detail?: unknown }) => (typeof json.detail === "string" ? json.detail : null),
      () => null,
    );
    throw new ApiError(response.status, detail, `${method} ${path} failed with ${response.status}`);
  }
```

with

```ts
  if (!response.ok) {
    throw await apiError(response, `${method} ${path} failed with ${response.status}`);
  }
```

and replace

```ts
export const apiPost = (path: string, body?: unknown, init: { keepalive?: boolean } = {}) =>
  send<void>("POST", path, body, init.keepalive);
```

with

```ts
export const apiPost = <T = void>(path: string, body?: unknown, init: { keepalive?: boolean } = {}) =>
  send<T>("POST", path, body, init.keepalive);
```

- [ ] **Step 6: The chat model**

Create `apps/web/src/lib/chat.ts`:

```ts
import { APICallError, type UIMessage } from "ai";

import { ApiError, type Schemas } from "@/lib/api";

export type Thread = Schemas["Thread"];
export type ChatMessage = Schemas["ChatMessage"];
export type QueryResult = Schemas["QueryResult"];

/** How an answer ended, and the user's thumbs. The history carries it; a live answer gets it
 * when its stream ends. */
export type AnswerMeta = { status: ChatMessage["status"]; feedback: ChatMessage["feedback"] };

/** `run_sql`'s output is a QueryResult, or only `{error}` when the per-turn query limit refused
 * the call (plan 4a, ui_stream.py). */
export type QueryOutput = QueryResult | { error: string };

/** The messages useChat holds: the API's stream parts (plan 4a, Task 9) typed for this app. */
export type ChatUIMessage = UIMessage<
  AnswerMeta,
  { title: { threadId: string; title: string } },
  { run_sql: { input: { sql: string }; output: QueryOutput } }
>;
export type ChatPart = ChatUIMessage["parts"][number];
export type QueryPart = Extract<ChatPart, { type: "tool-run_sql" }>;

/** The saved history as useChat messages. An answer's queries come before its text: the order
 * they streamed in (spec 9). */
export function toUIMessages(history: ChatMessage[]): ChatUIMessage[] {
  return history.map((message) => ({
    id: message.id,
    role: message.role,
    metadata: message.role === "assistant" ? { status: message.status, feedback: message.feedback } : undefined,
    parts: [
      ...message.queries.map(
        (query, index): QueryPart => ({
          type: "tool-run_sql",
          toolCallId: `${message.id}-${index}`,
          state: "output-available",
          input: { sql: query.sql },
          output: query,
        }),
      ),
      ...(message.content ? [{ type: "text" as const, text: message.content, state: "done" as const }] : []),
    ],
  }));
}

/** The body of POST /chat/threads/{id}/messages: the API keeps the history, so only the new
 * question travels (spec 10). */
export function newMessageBody(messages: ChatUIMessage[]): { text: string } {
  const last = messages.at(-1);
  if (last?.role !== "user") throw new Error("Only a new question can be sent");
  return { text: partsText(last) };
}

/** The question of a turn that got no answer at all (the API refused it, or was unreachable):
 * it goes back to the composer. Null when an answer started: the API saved that question. */
export function unanswered(messages: ChatUIMessage[]): string | null {
  const last = messages.at(-1);
  return last?.role === "user" ? partsText(last) : null;
}

const partsText = (message: ChatUIMessage) =>
  message.parts.map((part) => (part.type === "text" ? part.text : "")).join("");

export type Block = { kind: "text"; text: string; streaming: boolean } | { kind: "queries"; queries: QueryPart[] };

/** An answer in reading order: consecutive queries form one disclosure, text stays where it
 * streamed, and the title part (for the sidebar) is not shown. */
export function answerBlocks(parts: ChatPart[]): Block[] {
  const blocks: Block[] = [];
  for (const part of parts) {
    const last = blocks.at(-1);
    if (part.type === "tool-run_sql") {
      if (last?.kind === "queries") last.queries.push(part);
      else blocks.push({ kind: "queries", queries: [part] });
    } else if (part.type === "text" && part.text) {
      blocks.push({ kind: "text", text: part.text, streaming: part.state === "streaming" });
    }
  }
  return blocks;
}

/** While a turn runs, whether nothing on screen moves: no answer yet, or its queries are done
 * and the model is working on the next step. A running query shows its own spinner. */
export function isThinking(messages: ChatUIMessage[]): boolean {
  const last = messages.at(-1);
  if (last?.role !== "assistant") return true;
  const block = answerBlocks(last.parts).at(-1);
  if (!block) return true;
  return block.kind === "queries" && block.queries.every((query) => query.state === "output-available");
}

/** "8 rows", "No rows", or "First 200 rows (there were more)": what a query returned. */
export function rowsLabel(result: QueryResult): string {
  if (result.truncated) return `First ${result.row_count} rows (there were more)`;
  if (result.row_count === 0) return "No rows";
  return result.row_count === 1 ? "1 row" : `${result.row_count} rows`;
}

/** A query the per-turn limit refused: the API sends only `{error}`, without rows. */
export const isRefused = (output: QueryOutput): output is { error: string } => !("rows" in output);

const BUSY = "This chat is still answering. Wait for it or stop it first.";

/** A failed turn or chat request in words. The API's own sentences come through: the stream's
 * `error` part (plan 4a, ERROR_TEXT) and the 409 detail. */
export function chatErrorText(error: Error): string {
  const refused = refusal(error);
  if (refused?.status === 409) return refused.detail ?? BUSY;
  if (refused?.status === 404) return "This chat no longer exists. Start a new one.";
  if (refused?.status === 503) return "The chat is not set up: add XAI_API_KEY to .env and restart the API.";
  if (refused) return `The API refused the request (${refused.status}).`;
  if (error instanceof TypeError) return "Could not reach the API. Check that it is running (from apps/api: uv run task api).";
  return error.message || "Something went wrong while answering. Try again.";
}

/** The HTTP refusal behind an error: useChat's APICallError or our ApiError. */
function refusal(error: Error): { status: number; detail: string | null } | null {
  if (error instanceof ApiError) return { status: error.status, detail: error.detail };
  if (!APICallError.isInstance(error)) return null;
  try {
    const value = (JSON.parse(error.responseBody ?? "") as { detail?: unknown }).detail;
    return { status: error.statusCode ?? 0, detail: typeof value === "string" ? value : null };
  } catch {
    return { status: error.statusCode ?? 0, detail: null };
  }
}
```

Create `apps/web/src/lib/chat-threads.ts`:

```ts
import type { Thread } from "@/lib/chat";

/** A thread without a title yet: its first answer is still being written, or was stopped. Not
 * "New chat", which names the button that starts one. */
export const threadTitle = (thread: Thread) => thread.title ?? "Untitled chat";

/** The sidebar's list, newest activity first like GET /chat/threads: a thread that is created
 * or has just answered moves to the top (a rename keeps its place). */
export const putFirst = (threads: Thread[], thread: Thread) => [thread, ...threads.filter((t) => t.id !== thread.id)];

export const patchThread = (threads: Thread[], id: string, patch: Partial<Thread>) =>
  threads.map((thread) => (thread.id === id ? { ...thread, ...patch } : thread));

export const moveFirst = (threads: Thread[], id: string) => {
  const thread = threads.find((t) => t.id === id);
  return thread ? putFirst(threads, thread) : threads;
};

export const dropThread = (threads: Thread[], id: string) => threads.filter((thread) => thread.id !== id);
```

- [ ] **Step 7: The chat client**

Create `apps/web/src/lib/chat-api.ts`:

```ts
import { DefaultChatTransport } from "ai";

import { API_URL, apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api";
import { newMessageBody, type ChatMessage, type ChatUIMessage, type Thread } from "@/lib/chat";

/** The chat routes of plan 4a (Task 12). Every one answers 503 while the chat is not set up. */
export const listThreads = () => apiGet<Thread[]>("/chat/threads");
export const listMessages = (threadId: string) => apiGet<ChatMessage[]>(`/chat/threads/${threadId}/messages`);
export const createThread = () => apiPost<Thread>("/chat/threads");
export const renameThread = (threadId: string, title: string) => apiPatch<Thread>(`/chat/threads/${threadId}`, { title });
export const deleteThread = (threadId: string) => apiDelete(`/chat/threads/${threadId}`);
export const sendFeedback = (messageId: string, value: "up" | "down", comment?: string) =>
  apiPost(`/chat/messages/${messageId}/feedback`, { value, comment });

/** useChat's transport. A chat's id is its thread id; the answer streams from that thread's
 * messages route, and only the new question is sent (spec 10). */
export const chatTransport = new DefaultChatTransport<ChatUIMessage>({
  prepareSendMessagesRequest: ({ id, messages }) => ({
    api: `${API_URL}/chat/threads/${id}/messages`,
    body: newMessageBody(messages),
  }),
});
```

`prepareSendMessagesRequest` may return `api` as well as `body` (`ai` 7.0.137, `PrepareSendMessagesRequest`), so one transport serves every chat.

- [ ] **Step 8: Run the tests and the gate**

Run: `cd apps/web && npx vitest run src/lib/chat.test.ts src/lib/chat-threads.test.ts`
Expected: 18 passed.

Run: `cd apps/web && npm run lint && npx next typegen && npx tsc --noEmit && npm test && npm run build`
Expected: no errors; 90 tests pass.

- [ ] **Step 9: Commit**

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/src/app/globals.css apps/web/src/lib/api.ts apps/web/src/lib/chat.ts apps/web/src/lib/chat.test.ts apps/web/src/lib/chat-threads.ts apps/web/src/lib/chat-threads.test.ts apps/web/src/lib/chat-api.ts
git commit -m "feat: chat model, client and AI SDK dependencies for the web"
```

---

### Task 2: A scripted chat server for the browser checks

**Files:**
- Create: `apps/api/tests/scripted_chat_server.py`

**Interfaces:**
- Consumes: plan 4a's `open_chat(settings, models)`, `ChatModels(agent, summary, title)`, `finance.api.main.app`.
- Produces: `uv run python -m tests.scripted_chat_server --db-url <scratch URL> [--port 8001] [--disabled]` (run from `apps/api`): the real 4a API with scripted models. Keywords in the question: `hello` (text only), `slow` (one query, then 200 words at 0.25 s each), `fail` (the model raises), `error` (a query on an unknown column), `big` (500 rows), `two` (two queries); anything else gets one query and a Markdown answer with a table and "How I counted it". Titles are the question's first four words, 1.5 s later. `--disabled` answers 503 on every chat route.

- [ ] **Step 1: Write the server**

Create `apps/api/tests/scripted_chat_server.py`:

```python
"""The API with a scripted chat, to check the web chat without model calls (plan 4b, recipe R3).

    cd apps/api && CORS_ORIGINS='["http://localhost:3001"]' \
        uv run python -m tests.scripted_chat_server --port 8001 \
        --db-url postgresql://postgres:postgres@127.0.0.1:54322/scratch_review

It refuses any database whose name does not start with "scratch_": the chats it writes are test
data. Langfuse stays off. The agent answers from words in the question:

    hello  -> a one-line answer, no query
    slow   -> one query, then a long answer streamed word by word (to try Stop)
    fail   -> the model raises: the stream ends with an error part
    error  -> a query on an unknown column, then a short answer
    big    -> a query of 500 rows (the API keeps the first 200)
    two    -> two queries, then the answer
    other  -> one query, then a Markdown answer with a table and "How I counted it"

Titles take 1.5 s, so they arrive while the answer streams. --disabled serves the 503 of a chat
without an xAI key.
"""

import argparse
import asyncio
import json
import os
import sys

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

ANSWER = """You spent **1,234.56 €** in the period, across 14 movements.

| Group | Spent | Share |
|---|---:|---:|
| Housing | 700.00 € | 56.7% |
| Shopping | 334.56 € | 27.1% |
| Transport | 200.00 € | 16.2% |

### How I counted it
- Dates: the whole month.
- Accounts: all of them.
- Transfers between your accounts are out; refunds subtract."""

QUERIES = {
    "error": ["SELECT nope FROM transactions"],
    "big": ["SELECT n, n * 2 AS twice FROM generate_series(1, 500) AS n"],
    "two": [
        "SELECT DISTINCT merchant FROM transactions WHERE merchant ILIKE '%a%' LIMIT 20",
        "SELECT month, SUM(spend) AS spent FROM transactions GROUP BY month ORDER BY month",
    ],
    "other": [
        "SELECT month, category_group, SUM(spend) AS spent, COUNT(*) AS movements\n"
        "FROM transactions\nGROUP BY month, category_group\nORDER BY month, spent DESC"
    ],
}


def _turn(messages) -> tuple[str, int]:
    """The latest question's first keyword, and how many query results came after it."""
    index = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
    question = str(messages[index].content).lower()
    done = sum(isinstance(m, ToolMessage) for m in messages[index + 1 :])
    keywords = ("hello", "slow", "fail", "error", "big", "two")
    keyword = next((k for k in keywords if k in question), "other")
    return keyword, done


def _reply(messages) -> tuple[AIMessage, float]:
    """The scripted answer and the pause between streamed words."""
    keyword, done = _turn(messages)
    if keyword == "fail":
        raise RuntimeError("scripted model failure")
    if keyword == "hello":
        return AIMessage("Hello! Ask me about your spending, income or subscriptions."), 0.03
    queries = QUERIES.get(keyword, QUERIES["other"])
    if done < len(queries):
        call = {"name": "run_sql", "args": {"sql": queries[done]}, "id": f"call_{done}"}
        return AIMessage(content="", tool_calls=[call]), 0
    if keyword == "slow":
        return AIMessage(" ".join(f"word{n}" for n in range(200))), 0.25
    if keyword == "error":
        return AIMessage("I could not run that query: one of its columns does not exist."), 0.03
    return AIMessage(ANSWER), 0.03


class ScriptedAgent(BaseChatModel):
    """Streams its text word by word, like a provider, so Stop and auto-scroll can be tried."""

    @property
    def _llm_type(self) -> str:
        return "scripted-agent"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=_reply(messages)[0])])

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        message, pause = _reply(messages)
        if message.tool_calls:
            chunks = [
                {"name": c["name"], "args": json.dumps(c["args"]), "id": c["id"], "index": 0}
                for c in message.tool_calls
            ]
            yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=chunks))
            return
        for n, word in enumerate(message.content.split(" ")):
            await asyncio.sleep(pause)
            text = word if n == 0 else f" {word}"
            yield ChatGenerationChunk(message=AIMessageChunk(content=text))


class ScriptedTitle(BaseChatModel):
    """The first four words of the question, after 1.5 s."""

    @property
    def _llm_type(self) -> str:
        return "scripted-title"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        raise NotImplementedError("the chat calls the title model asynchronously")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        await asyncio.sleep(1.5)
        title = " ".join(str(messages[-1].content).split()[:4]).rstrip("?.!") or "Untitled"
        call = {"name": "ChatTitle", "args": {"title": title}, "id": "title"}
        return ChatResult(generations=[ChatGeneration(message=AIMessage("", tool_calls=[call]))])


async def serve(port: int, disabled: bool) -> None:
    import uvicorn

    from finance.agent.graph import ChatModels
    from finance.agent.runtime import open_chat
    from finance.api.main import app
    from finance.settings import get_settings

    agent = ScriptedAgent()
    async with open_chat(get_settings(), ChatModels(agent, agent, ScriptedTitle())) as chat:
        app.state.chat = None if disabled else chat
        config = uvicorn.Config(app, port=port, lifespan="off")
        await uvicorn.Server(config).serve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db-url", required=True, help="a scratch copy, never the real database")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--disabled", action="store_true", help="answer 503, as without a key")
    args = parser.parse_args()
    if not args.db_url.rsplit("/", 1)[-1].startswith("scratch_"):
        sys.exit("Refusing a database whose name does not start with scratch_ (see recipe R3).")
    # Before finance is imported: the settings and the Langfuse client read these once.
    os.environ["SUPABASE_DB_URL"] = args.db_url
    os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
    asyncio.run(serve(args.port, args.disabled))
```

It streams through `_astream` because LangGraph's `messages` stream mode asks the model to stream; the text then arrives word by word, as from a provider. pytest does not collect it (the name does not start with `test_`).

- [ ] **Step 2: Lint**

Run: `cd apps/api && uv run task lint && uv run task test`
Expected: clean; the unit suite passes unchanged.

- [ ] **Step 3: Check it refuses the real database**

Run: `cd apps/api && uv run python -m tests.scripted_chat_server --db-url postgresql://postgres:postgres@127.0.0.1:54322/postgres; echo "exit=$?"`
Expected: `Refusing a database whose name does not start with scratch_ (see recipe R3).` and `exit=1`.

- [ ] **Step 4: Check it streams on a scratch copy**

Make the scratch copy (R3 step 1) and start the server (R3 step 2). Then:

```bash
id=$(curl -s -X POST http://localhost:8001/chat/threads | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'); curl -s -X POST -H 'content-type: application/json' -d '{"text": "two please"}' "http://localhost:8001/chat/threads/$id/messages" | grep -o '"type": "[a-z-]*"' | sort | uniq -c
```

Expected: one `start`, two `tool-input-available`, two `tool-output-available`, one `text-start`, many `text-delta`, one `text-end`, one `data-title`, one `finish`.

Check Stop through real HTTP (P1, fixed in 4a):

```bash
id=$(curl -s -X POST http://localhost:8001/chat/threads | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'); curl -s -m 2 -X POST -H 'content-type: application/json' -d '{"text": "slow please"}' "http://localhost:8001/chat/threads/$id/messages" > /dev/null; sleep 2; PGPASSWORD=postgres psql -h 127.0.0.1 -p 54322 -U postgres scratch_review -tAc "select role, status from chat_messages where thread_id = '$id' order by created_at"
```

Expected: `user|ok` then `assistant|stopped`. Stop the server and drop the copy (R3 step 5).

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/scripted_chat_server.py
git commit -m "test: a scripted chat server for checking the web chat"
```

---

### Task 3: Open a saved chat

**Files:**
- Modify: `apps/web/src/app/layout.tsx`
- Create: `apps/web/src/app/chat/layout.tsx`, `apps/web/src/app/chat/[id]/page.tsx`
- Create: `apps/web/src/components/chat/chats-provider.tsx`, `thread-list.tsx`, `chat-header.tsx`, `query-disclosure.tsx`, `chat-message.tsx`, `conversation.tsx` (all under `apps/web/src/components/chat/`)

**Interfaces:**
- Consumes: Task 1 (`@/lib/chat`, `@/lib/chat-threads`, `@/lib/chat-api`, `ApiError`), `isUuid` from `@/lib/params`, the kit (`Button`, `Sheet*`, `Table*`, `Spinner`, `Empty*`).
- Produces:
  - the route `/chat/<id>` and the `/chat` layout (`/chat` itself comes in Task 5);
  - `ChatsProvider({ initialThreads, children })` and `useChats(): { threads, chatFor(threadId, history), added(thread), renamed(thread), deleted(threadId) }`. `chatFor` returns the same AI SDK `Chat` for a thread for the life of the layout; its `onData` puts a `data-title` into the list and its `onFinish` marks the answer `ok`, `stopped` or `error` (metadata) and moves the thread to the top. `added` is used by Task 5, `renamed` and `deleted` by Task 6;
  - `ChatHeader({ children })`: the title row, with the chats sheet below md;
  - `ThreadList({ onNavigate? })`, `QueryDisclosure({ queries })`, `ChatMessageView({ message, live })`, `Conversation({ threadId, history })`.

- [ ] **Step 1: Read the Next.js guides**

Read `apps/web/node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/layout.md`, `dynamic-routes.md` and `not-found.md`, and the "Route Segment Config" pages next to them. Facts this task relies on: a layout persists across navigations between its child pages (so the provider's state and the live `Chat`s survive the move from one chat to another); a layout may return a different tree instead of `children`; `params` is a Promise; `notFound()` from a page renders the 404.

- [ ] **Step 2: Let the chat fill the window**

The chat's messages scroll inside the page, between the top bar and the question box. The root layout's `body` is `min-h-full`, so it grows with its content; on the chat pages it gets the window's height and `main` may shrink. In `apps/web/src/app/layout.tsx`, replace

```tsx
      <body className="flex min-h-full flex-col">
```

with

```tsx
      {/* The chat fills the window exactly, so only its messages scroll (app/chat/layout.tsx). */}
      <body className="flex min-h-full flex-col has-data-[slot=chat-shell]:h-dvh">
```

and replace

```tsx
        <main id="main" className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 px-4 py-5 sm:px-6">{children}</main>
```

with

```tsx
        <main
          id="main"
          className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 px-4 py-5 has-data-[slot=chat-shell]:min-h-0 sm:px-6"
        >
          {children}
        </main>
```

- [ ] **Step 3: The chat's client state**

Create `apps/web/src/components/chat/chats-provider.tsx`:

```tsx
"use client";

import { Chat } from "@ai-sdk/react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { toUIMessages, type ChatMessage, type ChatUIMessage, type Thread } from "@/lib/chat";
import { chatTransport } from "@/lib/chat-api";
import { dropThread, moveFirst, patchThread, putFirst } from "@/lib/chat-threads";

type Chats = {
  threads: Thread[];
  /** The live conversation of a thread: the same instance across navigations, so an answer keeps
   * streaming when a new chat moves from /chat to /chat/<id> or the user opens another chat. */
  chatFor: (threadId: string, history: ChatMessage[]) => Chat<ChatUIMessage>;
  added: (thread: Thread) => void;
  renamed: (thread: Thread) => void;
  deleted: (threadId: string) => void;
};

const ChatsContext = createContext<Chats | null>(null);

export function useChats(): Chats {
  const chats = useContext(ChatsContext);
  if (!chats) throw new Error("useChats needs a ChatsProvider (app/chat/layout.tsx)");
  return chats;
}

/** The chat's client state for the /chat layout: the sidebar's threads and one useChat `Chat`
 * per opened thread. The layout's server fetch seeds the list; this keeps it current (new chats,
 * titles as they arrive, renames, deletions, the latest answer on top). */
export function ChatsProvider({ initialThreads, children }: { initialThreads: Thread[]; children: ReactNode }) {
  const [threads, setThreads] = useState(initialThreads);
  const [live] = useState(() => new Map<string, Chat<ChatUIMessage>>());

  const chatFor = useCallback(
    (threadId: string, history: ChatMessage[]) => {
      const existing = live.get(threadId);
      if (existing) return existing;
      const chat: Chat<ChatUIMessage> = new Chat<ChatUIMessage>({
        id: threadId,
        messages: toUIMessages(history),
        transport: chatTransport,
        onData: (part) => {
          if (part.type === "data-title") setThreads((all) => patchThread(all, part.data.threadId, { title: part.data.title }));
        },
        onFinish: ({ message, isAbort, isError }) => {
          if (!chat.messages.some((m) => m.id === message.id)) return; // refused before any answer
          // The answer is saved now: it can take feedback, and the thread moves to the top.
          const status = isAbort ? "stopped" : isError ? "error" : "ok";
          chat.messages = chat.messages.map((m) => (m.id === message.id ? { ...m, metadata: { status, feedback: null } } : m));
          setThreads((all) => moveFirst(all, threadId));
        },
      });
      live.set(threadId, chat);
      return chat;
    },
    [live],
  );

  const value = useMemo<Chats>(
    () => ({
      threads,
      chatFor,
      added: (thread) => setThreads((all) => putFirst(all, thread)),
      renamed: (thread) => setThreads((all) => patchThread(all, thread.id, thread)),
      deleted: (threadId) => {
        live.delete(threadId);
        setThreads((all) => dropThread(all, threadId));
      },
    }),
    [threads, chatFor, live],
  );
  return <ChatsContext.Provider value={value}>{children}</ChatsContext.Provider>;
}
```

The `Map` lives in state (not a ref), so reading it while rendering is allowed; `chatFor` is idempotent, which React's development double render needs. A chat opened earlier in the session shows the browser's copy of its messages, not a fresh read: a chat continued in another tab or in `finance chat` shows those turns after a reload.

- [ ] **Step 4: The saved chats**

Create `apps/web/src/components/chat/thread-list.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { threadTitle } from "@/lib/chat-threads";
import { cn } from "@/lib/utils";

import { useChats } from "./chats-provider";

/** The saved chats, newest activity first (spec 10). In the sidebar on wide screens and in a
 * sheet on phones; `onNavigate` closes the sheet. */
export function ThreadList({ onNavigate }: { onNavigate?: () => void }) {
  const { threads } = useChats();
  const pathname = usePathname();
  return (
    <nav aria-label="Chats" className="flex min-h-0 flex-col gap-3">
      {threads.length === 0 ? (
        <p className="px-3 text-sm text-muted-foreground">Your chats appear here.</p>
      ) : (
        <ul className="-mx-1 flex min-h-0 flex-col gap-0.5 overflow-y-auto px-1 pb-1">
          {threads.map((thread) => {
            const active = pathname === `/chat/${thread.id}`;
            return (
              <li key={thread.id}>
                <Link
                  href={`/chat/${thread.id}`}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "block truncate rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                    active && "bg-muted font-medium text-foreground",
                  )}
                >
                  {threadTitle(thread)}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </nav>
  );
}
```

Muted text on `bg-muted` is 4.59:1 (plan 3b, Decision B).

- [ ] **Step 5: The title row and the phone sheet**

Create `apps/web/src/components/chat/chat-header.tsx`:

```tsx
"use client";

import { PanelLeft } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

import { ThreadList } from "./thread-list";

// Picking a chat in the sheet opens a page with a new header, and the old trigger goes with the
// old page: the new trigger takes the focus, so it never drops to the page. Only when it did drop:
// picking the open chat keeps this header, and the flag outlives it.
let focusTriggerOnMount = false;

/** The chat's title row: the page's heading and actions. Below md the sidebar is a sheet,
 * opened from here. */
export function ChatHeader({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!focusTriggerOnMount) return;
    focusTriggerOnMount = false;
    if (document.activeElement === document.body) trigger.current?.focus();
  }, []);
  return (
    <header className="flex min-h-9 shrink-0 items-center gap-2">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger ref={trigger} render={<Button variant="ghost" size="icon" className="md:hidden" aria-label="Chats" />}>
          <PanelLeft />
        </SheetTrigger>
        <SheetContent side="left" className="data-[side=left]:w-72">
          <SheetHeader>
            <SheetTitle>Chats</SheetTitle>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col px-4 pb-4">
            <ThreadList
              onNavigate={() => {
                focusTriggerOnMount = true;
                setOpen(false);
              }}
            />
          </div>
        </SheetContent>
      </Sheet>
      {children}
    </header>
  );
}
```

- [ ] **Step 6: The queries behind an answer**

Create `apps/web/src/components/chat/query-disclosure.tsx`:

```tsx
"use client";

import { ChevronRight } from "lucide-react";
import { useStickToBottomContext } from "use-stick-to-bottom";

import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { isRefused, rowsLabel, type QueryOutput, type QueryPart } from "@/lib/chat";

/** The queries behind an answer (spec 10): closed by default, each with its SQL and the rows it
 * returned, or its error. The answer itself never names tables or SQL (spec 6). */
export function QueryDisclosure({ queries }: { queries: QueryPart[] }) {
  // Opening it grows the conversation: without this, stick-to-bottom would scroll the queries
  // the user asked to read out of view. Scrolling back down (or the arrow) re-attaches.
  const { stopScroll } = useStickToBottomContext();
  const running = queries.some((query) => query.state !== "output-available");
  const outputs = queries.flatMap((query) => (query.state === "output-available" ? [query.output] : []));
  const failed = outputs.filter((output) => !isRefused(output) && output.error).length;
  const notRun = outputs.filter(isRefused).length;
  const notes = [failed ? `${failed} failed` : "", notRun ? `${notRun} not run` : ""].filter(Boolean).join(", ");
  const count = queries.length === 1 ? "1 query" : `${queries.length} queries`;
  return (
    <details className="group rounded-xl bg-card text-sm">
      <summary onClick={stopScroll} className="flex cursor-pointer list-none items-center gap-2 rounded-xl px-3 py-2 text-muted-foreground hover:text-foreground [&::-webkit-details-marker]:hidden">
        <ChevronRight aria-hidden className="size-4 shrink-0 transition-transform group-open:rotate-90" />
        {running ? <Spinner /> : null}
        <span>
          {running ? "Running a query…" : `Ran ${count}`}
          {notes ? ` (${notes})` : null}
        </span>
      </summary>
      <ol className="flex flex-col gap-4 px-3 pb-3">
        {queries.map((query, index) => (
          <li key={query.toolCallId} className="flex min-w-0 flex-col gap-2">
            <p className="text-xs font-medium text-muted-foreground">Query {index + 1}</p>
            <pre className="overflow-x-auto rounded-lg bg-background p-3 font-mono text-xs leading-relaxed">
              <code>{query.input?.sql}</code>
            </pre>
            {query.state === "output-available" ? <QueryOutputView output={query.output} /> : null}
          </li>
        ))}
      </ol>
    </details>
  );
}

function QueryOutputView({ output }: { output: QueryOutput }) {
  if (isRefused(output)) return <p className="text-muted-foreground">Not run: this answer had already used its query limit.</p>;
  if (output.error) return <p className="text-bad">This query failed: {output.error}</p>;
  return (
    <>
      {output.rows.length > 0 ? (
        // The kit's Table wraps itself in an overflow-x-auto box, which is the sticky header's scroll
        // container: that box gets the height limit, so the header stays visible (found in 4b Task 3).
        <div className="overflow-hidden rounded-lg bg-background *:data-[slot=table-container]:max-h-72">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                {output.columns.map((column, index) => (
                  <TableHead key={index} className="sticky top-0 bg-background normal-case">
                    {column}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {output.rows.map((row, rowIndex) => (
                <TableRow key={rowIndex}>
                  {row.map((value, index) => (
                    <TableCell key={index} className="font-mono text-xs">
                      {value}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
      <p className="text-xs text-muted-foreground">{rowsLabel(output)}</p>
    </>
  );
}
```

A native `<details>` is keyboard- and screen-reader-ready with no script. `stopScroll` runs on the summary's click, before the element opens and grows: `use-stick-to-bottom` only follows growth while it is at the bottom. Columns keep their SQL names (`normal-case` undoes the table head's capitals); keys are indexes because two columns may share a name (plan 4a, Review Focus 4).

- [ ] **Step 7: A message**

Create `apps/web/src/components/chat/chat-message.tsx`:

```tsx
"use client";

import { Streamdown } from "streamdown";

import { answerBlocks, type ChatUIMessage } from "@/lib/chat";

import { QueryDisclosure } from "./query-disclosure";

type Props = {
  message: ChatUIMessage;
  /** The answer that is streaming now: its markdown is still incomplete. */
  live: boolean;
};

/** One message: the user's question as a bubble, or an answer as markdown with its queries. */
export function ChatMessageView({ message, live }: Props) {
  if (message.role === "user") {
    const text = message.parts.map((part) => (part.type === "text" ? part.text : "")).join("");
    return <div className="ml-auto max-w-[85%] rounded-2xl bg-card px-4 py-2.5 whitespace-pre-wrap wrap-anywhere">{text}</div>;
  }
  const meta = message.metadata;
  return (
    <article aria-label="Answer" className="flex min-w-0 flex-col gap-3">
      {answerBlocks(message.parts).map((block, index) =>
        block.kind === "queries" ? (
          <QueryDisclosure key={index} queries={block.queries} />
        ) : (
          <Streamdown
            key={index}
            isAnimating={live && block.streaming}
            controls={false}
            // Headings stay small: an answer's "How I counted it" is a note, not a page title.
            className="[&_:is(h1,h2,h3,h4)]:mt-4 [&_:is(h1,h2,h3,h4)]:text-base"
          >
            {block.text}
          </Streamdown>
        ),
      )}
      {meta?.status === "stopped" ? <p className="text-sm text-muted-foreground">You stopped this answer.</p> : null}
      {meta?.status === "error" ? <p className="text-sm text-muted-foreground">This answer did not finish.</p> : null}
    </article>
  );
}
```

Streamdown closes unfinished markdown while text streams (a half-written table or `**bold`) and sanitizes it (its default rehype plugins). `controls={false}` hides its copy and download buttons on tables. Its h3 is `text-xl` by default; the arbitrary variant (one class plus the element) outranks it.

- [ ] **Step 8: The conversation (reading)**

Create `apps/web/src/components/chat/conversation.tsx`:

```tsx
"use client";

import { useChat } from "@ai-sdk/react";
import { ArrowDown } from "lucide-react";
import { useState } from "react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";

import { Button } from "@/components/ui/button";
import type { ChatMessage } from "@/lib/chat";
import { threadTitle } from "@/lib/chat-threads";

import { ChatHeader } from "./chat-header";
import { ChatMessageView } from "./chat-message";
import { useChats } from "./chats-provider";

/** One chat and its full history (spec 8). */
export function Conversation({ threadId, history }: { threadId: string; history: ChatMessage[] }) {
  const { threads, chatFor } = useChats();
  const [chat] = useState(() => chatFor(threadId, history));
  const { messages } = useChat({ chat });
  const thread = threads.find((t) => t.id === threadId);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <ChatHeader>
        <h1 className="min-w-0 flex-1 truncate font-semibold tracking-tight">{thread ? threadTitle(thread) : "Chat"}</h1>
      </ChatHeader>
      <StickToBottom
        className="relative min-h-0 flex-1 rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        initial="instant"
        resize="smooth"
        role="log"
        aria-label="Conversation"
        tabIndex={-1}
      >
        <StickToBottom.Content className="mx-auto flex w-full max-w-3xl flex-col gap-6 py-2">
          {messages.map((message) => (
            <ChatMessageView key={message.id} message={message} live={false} />
          ))}
        </StickToBottom.Content>
        <ScrollToLatest />
      </StickToBottom>
    </div>
  );
}

function ScrollToLatest() {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();
  if (isAtBottom) return null;
  return (
    <Button
      variant="outline"
      size="icon"
      aria-label="Scroll to the latest message"
      className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full shadow-sm"
      onClick={(event) => {
        // The button disappears once the view is at the bottom: focus moves to the conversation
        // first, so it never drops to the page.
        event.currentTarget.closest<HTMLElement>("[role=log]")?.focus({ preventScroll: true });
        void scrollToBottom();
      }}
    >
      <ArrowDown />
    </Button>
  );
}
```

`StickToBottom` renders an outer box (`relative`, it receives `role` and the label), a scrolling box and the content box (`StickToBottom.Content`'s `className`); `initial="instant"` opens a long chat at its end without animating.

- [ ] **Step 9: The chat layout**

Create `apps/web/src/app/chat/layout.tsx`:

```tsx
import type { Metadata } from "next";

import { ChatsProvider } from "@/components/chat/chats-provider";
import { ThreadList } from "@/components/chat/thread-list";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { ApiError } from "@/lib/api";
import { listThreads } from "@/lib/chat-api";
import type { Thread } from "@/lib/chat";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Chat" };

/** The chat (spec 10): saved chats on the left, the open chat on the right. It fills the window
 * below the top bar (the root layout's `has-data-[slot=chat-shell]` classes), so only the
 * messages scroll. Without an xAI key the API answers 503 and the page says how to set it up. */
export default async function ChatLayout({ children }: LayoutProps<"/chat">) {
  let threads: Thread[];
  try {
    threads = await listThreads();
  } catch (error) {
    if (error instanceof ApiError && error.status === 503) return <NotConfigured />;
    throw error;
  }
  return (
    <ChatsProvider initialThreads={threads}>
      <div data-slot="chat-shell" className="flex min-h-0 flex-1 gap-6">
        <aside className="hidden w-60 shrink-0 flex-col md:flex">
          <ThreadList />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">{children}</div>
      </div>
    </ChatsProvider>
  );
}

function NotConfigured() {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyTitle render={<h1 />}>The chat is not set up yet</EmptyTitle>
        <EmptyDescription>
          It needs an xAI API key. Add XAI_API_KEY to the .env file at the repo root, then restart the API (from apps/api: uv
          run task api).
        </EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}
```

Any other failure (the API stopped) is thrown to `app/error.tsx` ("This page could not load"). The top bar's filters already stay off `/chat`: `FilterBar` shows only on `/` and its `FILTERED` pages.

- [ ] **Step 10: A saved chat's page**

Create `apps/web/src/app/chat/[id]/page.tsx`:

```tsx
import { notFound } from "next/navigation";

import { Conversation } from "@/components/chat/conversation";
import { ApiError } from "@/lib/api";
import { listMessages } from "@/lib/chat-api";
import type { ChatMessage } from "@/lib/chat";
import { isUuid } from "@/lib/params";

export const dynamic = "force-dynamic";

/** One saved chat with its full history (spec 8). A deleted or unknown chat is a 404. */
export default async function ChatPage({ params }: PageProps<"/chat/[id]">) {
  const { id } = await params;
  if (!isUuid(id)) notFound();
  let history: ChatMessage[];
  try {
    history = await listMessages(id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  return <Conversation key={id} threadId={id} history={history} />;
}
```

`key={id}` gives each chat its own component state when the user moves between chats; the live `Chat` itself comes from the provider.

- [ ] **Step 11: Run the gate**

Run: `cd apps/web && npm run lint && npx next typegen && npx tsc --noEmit && npm test && npm run build`
Expected: no errors; the build lists `ƒ /chat/[id]`.

- [ ] **Step 12: Check it in the browser (R3)**

Set up R3 (steps 1 to 3). Create saved chats through the API (the page cannot ask yet); `slow` is cut by curl after 2 s, as a closed tab would:

```bash
for q in "two please" "big please" "error please" "fail please" "hello"; do id=$(curl -s -X POST http://localhost:8001/chat/threads | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'); curl -s -X POST -H 'content-type: application/json' -d "{\"text\": \"$q\"}" "http://localhost:8001/chat/threads/$id/messages" > /dev/null; echo "$q -> http://localhost:3001/chat/$id"; done
id=$(curl -s -X POST http://localhost:8001/chat/threads | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'); curl -s -m 2 -X POST -H 'content-type: application/json' -d '{"text": "slow please"}' "http://localhost:8001/chat/threads/$id/messages" > /dev/null; echo "slow -> http://localhost:3001/chat/$id"
```

With the session `slice4b-scratch`:

1. Open the `two please` chat, `snapshot -i`. Expect: no filter pills in the top bar; a navigation "Chats" listing the chats by title, the six new ones first (the scripted titles: "two please", "big please"…; chats copied from the real database follow), the open one with `aria-current="page"`; an h1 "two please"; the question as a bubble on the right; a closed "Ran 2 queries"; the answer with a table (Group, Spent, Share) and a small "How I counted it" heading over three bullets.
2. Screenshot `$(git rev-parse --show-toplevel)/dogfood-output/slice-4b/task3-chat.png` (create the folder first) and read it: the bubble on a soft surface, the answer as plain text, nothing cut at the right.
3. The disclosure stays where it was clicked (Review Focus 4):

```bash
cat <<'EOF' | agent-browser --session slice4b-scratch eval --stdin
(async () => {
  const summary = document.querySelector("summary");
  const before = Math.round(summary.getBoundingClientRect().top);
  summary.click();
  await new Promise((resolve) => setTimeout(resolve, 800));
  return { before, after: Math.round(summary.getBoundingClientRect().top), open: summary.parentElement.open };
})()
EOF
```

Expected: `before` equals `after`, `open` is `true`. Snapshot: "Query 1" and "Query 2", each with its SQL and either "No rows" or a table with its column names in lower case and an "N rows" line.
4. The `big please` chat: open "Ran 1 query": the rows scroll inside a box whose header stays visible, under it "First 200 rows (there were more)".
5. The `error please` chat: "Ran 1 query (1 failed)"; open it: `This query failed: column "nope" does not exist`; then the answer text.
6. The `fail please` chat: the question, then "This answer did not finish." and no answer text.
7. The `slow` chat: "word0 word1 …" and "You stopped this answer." (needs P1; without it only the question shows: stop and report).
8. `open "http://localhost:3001/chat/00000000-0000-4000-8000-000000000000"` and `open "http://localhost:3001/chat/not-a-uuid"`: both the 404 page.
9. A short window: `set viewport 1280 480`, open the `two please` chat, then `eval "document.documentElement.scrollHeight > window.innerHeight"`: `false` (only the messages and the chat list scroll). `set viewport 1280 900`.
10. A phone: `set viewport 390 844`, reload. The sidebar is gone; a "Chats" button sits left of the title. `click "button[aria-label='Chats']"`: a sheet titled "Chats" lists the chats; click another one: it opens and the sheet closes. `eval "document.documentElement.scrollWidth > window.innerWidth"`: `false`. Screenshot `task3-phone.png`. `set viewport 1280 900`.
11. Stop the scripted API and start it again with `--disabled` (same command plus `--disabled`); reload: the h1 "The chat is not set up yet" and the XAI_API_KEY sentence. Stop it: reload shows "This page could not load". Start it again without `--disabled`.
12. `errors` (expected: none), `close`. Finish R3 (step 5).

- [ ] **Step 13: Commit**

```bash
git add apps/web/src/app/layout.tsx apps/web/src/app/chat apps/web/src/components/chat
git commit -m "feat: open saved chats with their answers and queries"
```

---

### Task 4: Ask, stream and stop

**Files:**
- Create: `apps/web/src/components/chat/composer.tsx`
- Modify: `apps/web/src/components/chat/conversation.tsx` (whole file below)

**Interfaces:**
- Consumes: Task 1 (`chatErrorText`, `isThinking`, `unanswered`), Task 3 (`useChats`, `ChatHeader`, `ChatMessageView`).
- Produces: `Composer({ value, onChange, onSend(text), answering, onStop?, pending? })` (Task 5 reuses it with `pending`); `Conversation` that sends, streams, stops and reports errors.

- [ ] **Step 1: The question box**

Create `apps/web/src/components/chat/composer.tsx`:

```tsx
"use client";

import { ArrowUp, Square } from "lucide-react";
import type { KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

const TEXT_MAX = 4000; // NewMessage.text: 1-4000 characters (plan 4a, Task 12)

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSend: (text: string) => void;
  /** An answer is on its way: the button stops it instead of sending. */
  answering: boolean;
  onStop?: () => void;
  /** A request that is not an answer (creating the chat) is running. */
  pending?: boolean;
};

/** The question box: Enter sends, Shift+Enter starts a new line, and Stop ends an answer. */
export function Composer({ value, onChange, onSend, answering, onStop, pending = false }: Props) {
  const text = value.trim();
  const canSend = text.length > 0 && !answering && !pending;

  function submit(event: { preventDefault: () => void }) {
    event.preventDefault();
    if (canSend) onSend(text);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Not while an input method composes a character (Japanese, Chinese…).
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) submit(event);
  }

  return (
    <form onSubmit={submit} className="flex shrink-0 items-end gap-2 rounded-2xl border border-input bg-background p-2 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
      <label htmlFor="chat-question" className="sr-only">
        Your question
      </label>
      <Textarea
        id="chat-question"
        value={value}
        maxLength={TEXT_MAX}
        rows={1}
        placeholder="Ask about your money"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onKeyDown}
        className="max-h-48 min-h-9 resize-none border-0 px-2 shadow-none focus-visible:ring-0"
      />
      {answering ? (
        <Button type="button" size="icon" variant="secondary" onClick={onStop} aria-label="Stop the answer">
          <Square />
        </Button>
      ) : (
        <Button type="submit" size="icon" disabled={!canSend} aria-label="Send">
          {pending ? <Spinner /> : <ArrowUp />}
        </Button>
      )}
    </form>
  );
}
```

The kit's `Textarea` grows with its text (`field-sizing-content`) up to `max-h-48`. Its own focus ring is off; the form shows the ring for the whole box. The text stays editable while an answer streams, so the next question can be typed.

- [ ] **Step 2: The conversation sends and stops**

Replace `apps/web/src/components/chat/conversation.tsx` with:

```tsx
"use client";

import { useChat } from "@ai-sdk/react";
import { ArrowDown } from "lucide-react";
import { useState } from "react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";

import { Button } from "@/components/ui/button";
import { chatErrorText, isThinking, unanswered, type ChatMessage } from "@/lib/chat";
import { threadTitle } from "@/lib/chat-threads";

import { ChatHeader } from "./chat-header";
import { ChatMessageView } from "./chat-message";
import { useChats } from "./chats-provider";
import { Composer } from "./composer";

/** One chat: its history, the streaming answer, and the question box (spec 10). */
export function Conversation({ threadId, history }: { threadId: string; history: ChatMessage[] }) {
  const { threads, chatFor } = useChats();
  const [chat] = useState(() => chatFor(threadId, history));
  const { messages, status, error, sendMessage, stop, setMessages } = useChat({ chat });
  const [draft, setDraft] = useState("");
  const answering = status === "submitted" || status === "streaming";
  const thread = threads.find((t) => t.id === threadId);
  const last = messages.at(-1);
  const thinking = answering && isThinking(messages);

  async function send(text: string) {
    setDraft("");
    await sendMessage({ text });
    // A question the API refused or never got goes back to the box, to send again.
    const question = chat.status === "error" ? unanswered(chat.messages) : null;
    if (question !== null) {
      setMessages(chat.messages.slice(0, -1));
      setDraft(question);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <ChatHeader>
        <h1 className="min-w-0 flex-1 truncate font-semibold tracking-tight">{thread ? threadTitle(thread) : "Chat"}</h1>
      </ChatHeader>
      <StickToBottom
        className="relative min-h-0 flex-1 rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        initial="instant"
        resize="smooth"
        role="log"
        aria-label="Conversation"
        aria-busy={answering}
        tabIndex={-1}
      >
        <StickToBottom.Content className="mx-auto flex w-full max-w-3xl flex-col gap-6 py-2">
          {messages.map((message) => (
            <ChatMessageView key={message.id} message={message} live={answering && message === last} />
          ))}
          {thinking ? <p className="shimmer text-sm">Thinking…</p> : null}
          {error ? (
            <p role="alert" className="rounded-xl bg-card px-4 py-3 text-sm text-bad">
              {chatErrorText(error)}
            </p>
          ) : null}
        </StickToBottom.Content>
        <ScrollToLatest />
      </StickToBottom>
      <div className="mx-auto w-full max-w-3xl">
        <Composer value={draft} onChange={setDraft} onSend={send} answering={answering} onStop={() => void stop()} />
      </div>
    </div>
  );
}

function ScrollToLatest() {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();
  if (isAtBottom) return null;
  return (
    <Button
      variant="outline"
      size="icon"
      aria-label="Scroll to the latest message"
      className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full shadow-sm"
      onClick={(event) => {
        // The button disappears once the view is at the bottom: focus moves to the conversation
        // first, so it never drops to the page.
        event.currentTarget.closest<HTMLElement>("[role=log]")?.focus({ preventScroll: true });
        void scrollToBottom();
      }}
    >
      <ArrowDown />
    </Button>
  );
}
```

How it behaves, as validated:

- `sendMessage` resolves when the turn ends, failed or not; useChat catches the error and sets `status` and `error` itself. An HTTP refusal leaves the question as the last message (`unanswered`), so it goes back to the box; once the stream started (`start` creates the answer), the API saved the question, so it stays.
- `stop()` aborts the request; the API cancels the turn and saves it as `stopped` (P1). The `Chat`'s `onFinish` (Task 3) marks the live answer `stopped`, so "You stopped this answer." shows at once, as after a reload.
- `aria-busy` keeps screen readers from reading every streamed word of the `log`; `shimmer` is shadcn's utility (`shadcn/tailwind.css`), and the reduced-motion rule in `globals.css` stills it.

- [ ] **Step 3: Run the gate**

Run: `cd apps/web && npm run lint && npx next typegen && npx tsc --noEmit && npm test && npm run build`
Expected: no errors.

- [ ] **Step 4: Check it in the browser (R3): asking**

Set up R3 and create a `hello` chat with the curl loop of Task 3 (only `"hello"`). With the session `slice4b-scratch`, open it:

1. Type `hello again` and press Enter: the bubble appears, the box empties, the answer streams, and the chat moves to the top of the list.
2. Type `line one`, press Shift+Enter, type `line two`: `eval "document.querySelector('#chat-question').value"` is `"line one\nline two"`. Press Enter: one bubble with two lines.
3. Ask `how much in total`: "Thinking…" shimmers, the summary reads "Running a query…" with a spinner, then "Ran 1 query", and the answer streams while the view follows it. Ask it again and scroll up during the answer: the view stops following and the "Scroll to the latest message" arrow appears; click it: back at the bottom.

- [ ] **Step 5: Check Stop (Review Focus 1)**

Ask `slow please`. When `word3` shows (`wait --text "word3"`), `click "[aria-label='Stop the answer']"`: the button turns back into Send, the partial text stays, and "You stopped this answer." appears. Reload: the same partial text and note (P1). Ask `hello`: it is answered (the chat is usable).

- [ ] **Step 6: Check a failed answer**

Ask `please fail`: an alert "Something went wrong while answering. Try again." and "This answer did not finish." under the question; the box is empty (the API kept the question). Ask `hello`: answered, and the alert is gone.

- [ ] **Step 7: Check a refused question (Review Focus 2)**

Start a slow turn on the same chat from a second terminal (the open chat's id is in the URL):

```bash
curl -s -m 30 -X POST -H 'content-type: application/json' -d '{"text": "slow from another tab"}' http://localhost:8001/chat/threads/<id>/messages > /dev/null &
```

Within 25 s, ask `Is this busy?` on the page: an alert "This chat is still answering. Wait for it or stop it first.", no bubble for it, and the box holds `Is this busy?` again.

- [ ] **Step 8: Check leaving a chat mid-answer (Review Focus 3)**

Ask `slow while I browse`; when `word2` shows, click another chat in the sidebar, wait 2 s, click this chat again: the answer is further on (a higher `wordN`) and still streaming, with Stop shown. Stop it.

- [ ] **Step 9: Check a phone (Review Focus 5)**

`set viewport 390 844`. Ask `hello ES` followed by 120 nines (`python3 -c "print('hello ES' + '9' * 120)"` prints it): the bubble wraps it, and `eval "document.documentElement.scrollWidth > window.innerWidth"` is `false`. Screenshot `task4-phone.png`. `set viewport 1280 900`, `errors` (none), `close`. Finish R3.

- [ ] **Step 10: Commit**

```bash
git add apps/web/src/components/chat/composer.tsx apps/web/src/components/chat/conversation.tsx
git commit -m "feat: ask in a chat, stream the answer and stop it"
```

---

### Task 5: Start a new chat

**Files:**
- Create: `apps/web/src/components/chat/new-chat.tsx`, `apps/web/src/app/chat/page.tsx`
- Modify: `apps/web/src/components/chat/thread-list.tsx` (whole file below), `apps/web/src/components/shell/nav-links.tsx`

**Interfaces:**
- Consumes: `createThread` (Task 1), `useChats().added` and `chatFor` (Task 3), `ChatHeader` (Task 3), `Composer` (Task 4).
- Produces: the route `/chat`; `NewChat`; "New chat" in the chat list; "Chat" in the main navigation.

- [ ] **Step 1: The new chat**

Create `apps/web/src/components/chat/new-chat.tsx`:

```tsx
"use client";

import { MessagesSquare } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { chatErrorText } from "@/lib/chat";
import { createThread } from "@/lib/chat-api";

import { ChatHeader } from "./chat-header";
import { useChats } from "./chats-provider";
import { Composer } from "./composer";

const EXAMPLES = [
  "How much did I spend last month?",
  "Which merchants did I spend the most at this year?",
  "What are my active subscriptions and what do they cost per month?",
  "Compare my spending by group this month with last month.",
];

/** /chat: a new chat. The thread is created with the first question, whose answer starts
 * streaming here and goes on in /chat/<id> (the same useChat `Chat`, from ChatsProvider). */
export function NewChat() {
  const { added, chatFor } = useChats();
  const router = useRouter();
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start(text: string) {
    setPending(true);
    setError(null);
    try {
      const thread = await createThread();
      added(thread);
      void chatFor(thread.id, []).sendMessage({ text });
      router.push(`/chat/${thread.id}`);
    } catch (failure) {
      setError(chatErrorText(failure instanceof Error ? failure : new Error(String(failure))));
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <ChatHeader>
        <h1 className="min-w-0 flex-1 truncate font-semibold tracking-tight">New chat</h1>
      </ChatHeader>
      <Empty className="min-h-0 justify-center-safe overflow-y-auto">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <MessagesSquare />
          </EmptyMedia>
          <EmptyTitle>Ask about your money</EmptyTitle>
          <EmptyDescription>
            Answers come from your imported statements, with how they were counted. Each answer shows the queries it ran.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent className="max-w-md">
          {EXAMPLES.map((example) => (
            <Button
              key={example}
              variant="secondary"
              className="h-auto w-full justify-start py-2 text-left text-pretty whitespace-normal"
              disabled={pending}
              onClick={() => start(example)}
            >
              {example}
            </Button>
          ))}
        </EmptyContent>
      </Empty>
      {error ? (
        <p role="alert" className="mx-auto w-full max-w-3xl rounded-xl bg-card px-4 py-3 text-sm text-bad">
          {error}
        </p>
      ) : null}
      <div className="mx-auto w-full max-w-3xl">
        <Composer value={draft} onChange={setDraft} onSend={start} answering={false} pending={pending} />
      </div>
    </div>
  );
}
```

The thread is created only when a question is sent, so leaving `/chat` never leaves an empty chat behind. The question is sent on the provider's `Chat` before the navigation, so the stream started here is the one `/chat/<id>` shows. `justify-center-safe` keeps the empty state's top reachable when a short window makes it scroll (plain centring would cut it).

- [ ] **Step 2: The `/chat` page**

Create `apps/web/src/app/chat/page.tsx`:

```tsx
import { NewChat } from "@/components/chat/new-chat";

/** A new chat: example questions and the question box (spec 10). */
export default function NewChatPage() {
  return <NewChat />;
}
```

It fetches nothing itself (the layout fetches the list and is `force-dynamic`).

- [ ] **Step 3: "New chat" in the chat list**

Replace `apps/web/src/components/chat/thread-list.tsx` with:

```tsx
"use client";

import { SquarePen } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { buttonVariants } from "@/components/ui/button";
import { threadTitle } from "@/lib/chat-threads";
import { cn } from "@/lib/utils";

import { useChats } from "./chats-provider";

/** New chat and the saved chats, newest activity first (spec 10). In the sidebar on wide
 * screens and in a sheet on phones; `onNavigate` closes the sheet. */
export function ThreadList({ onNavigate }: { onNavigate?: () => void }) {
  const { threads } = useChats();
  const pathname = usePathname();
  return (
    <nav aria-label="Chats" className="flex min-h-0 flex-col gap-3">
      <Link href="/chat" onClick={onNavigate} className={cn(buttonVariants({ variant: "outline" }), "justify-start")}>
        <SquarePen data-icon="inline-start" />
        New chat
      </Link>
      {threads.length === 0 ? (
        <p className="px-3 text-sm text-muted-foreground">Your chats appear here.</p>
      ) : (
        <ul className="-mx-1 flex min-h-0 flex-col gap-0.5 overflow-y-auto px-1 pb-1">
          {threads.map((thread) => {
            const active = pathname === `/chat/${thread.id}`;
            return (
              <li key={thread.id}>
                <Link
                  href={`/chat/${thread.id}`}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "block truncate rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                    active && "bg-muted font-medium text-foreground",
                  )}
                >
                  {threadTitle(thread)}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </nav>
  );
}
```

- [ ] **Step 4: "Chat" in the navigation**

In `apps/web/src/components/shell/nav-links.tsx`, after the `/subscriptions` item, add:

```tsx
  { href: "/chat", label: "Chat", keepsFilters: false, active: (path) => path.startsWith("/chat") },
```

- [ ] **Step 5: Run the gate**

Run: `cd apps/web && npm run lint && npx next typegen && npx tsc --noEmit && npm test && npm run build`
Expected: no errors; the build lists `ƒ /chat` and `ƒ /chat/[id]`.

- [ ] **Step 6: Check it in the browser (R3)**

Set up R3. With the session `slice4b-scratch`:

1. `open "http://localhost:3001/"`: the main navigation reads Overview, Transactions, Subscriptions, Chat, Review, Imports, Settings. Click Chat: `/chat`, Chat has `aria-current="page"`, no filter pills; the h1 "New chat"; "Ask about your money" with the explanation and four example buttons; the box "Ask about your money" with Send disabled; "New chat" at the top of the chat list.
2. Click "How much did I spend last month?": the URL becomes `/chat/<uuid>`; the question bubble, "Thinking…", then the answer streams without a break; the new chat sits at the top of the list as "Untitled chat" and, about 1.5 s later, as "How much did I" in the list and the h1 (the live title, spec 8). Screenshot `task5-new-chat.png`.
3. Click "New chat", type `two queries please`, press Enter: the same flow, "Ran 2 queries", the new chat on top (Review Focus 3).
4. Click "New chat", ask `slow from a new chat`; when `word2` shows, Stop: "You stopped this answer."; reload: still there (P1). The list shows "Untitled chat" for it until the reload (P3).
5. A short window: `set viewport 1280 480`, `open "http://localhost:3001/chat"`: the empty state scrolls inside its area and its icon is reachable (`eval "getComputedStyle(document.querySelector('[data-slot=empty]')).justifyContent"` is `"safe center"`). `set viewport 1280 900`.
6. A phone: `set viewport 390 844`, `/chat`: the examples wrap inside the screen; open the sheet, click "New chat": the sheet closes. `set viewport 1280 900`, `errors` (none), `close`. Finish R3.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/chat/new-chat.tsx apps/web/src/app/chat/page.tsx apps/web/src/components/chat/thread-list.tsx apps/web/src/components/shell/nav-links.tsx
git commit -m "feat: start a new chat from /chat and the navigation"
```

---

### Task 6: Rename, delete and rate

**Files:**
- Create: `apps/web/src/components/chat/thread-header.tsx`, `apps/web/src/components/chat/feedback-buttons.tsx`
- Modify: `apps/web/src/components/chat/chat-message.tsx`, `apps/web/src/components/chat/conversation.tsx` (whole files below)

**Interfaces:**
- Consumes: `renameThread`, `deleteThread`, `sendFeedback` (Task 1); `useChats().renamed` and `deleted` (Task 3); `ChatHeader` (Task 3).
- Produces: `ThreadHeader({ thread, answering })`, `FeedbackButtons({ messageId, value, onSaved })`, `ChatMessageView({ message, live, onFeedback })`.

- [ ] **Step 1: The open chat's title row**

Create `apps/web/src/components/chat/thread-header.tsx`:

```tsx
"use client";

import { Pencil, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { flushSync } from "react-dom";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import type { Thread } from "@/lib/chat";
import { deleteThread, renameThread } from "@/lib/chat-api";
import { threadTitle } from "@/lib/chat-threads";

import { ChatHeader } from "./chat-header";
import { useChats } from "./chats-provider";

const TITLE_MAX = 200; // RenameThread.title: 1-200 characters (plan 4a, Task 12)

/** The open chat's title, live as it arrives, with Rename and Delete (spec 8 and 10). Delete
 * waits for the answer to end: the API refuses it with 409 while the chat answers. */
export function ThreadHeader({ thread, answering }: { thread: Thread; answering: boolean }) {
  const { renamed, deleted } = useChats();
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const renameButton = useRef<HTMLButtonElement>(null);

  function stopEditing() {
    // The field goes away: keyboard focus returns to Rename instead of the page.
    flushSync(() => setEditing(false));
    renameButton.current?.focus();
  }

  async function onRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      renamed(await renameThread(thread.id, title.trim()));
      stopEditing();
    } catch {
      toast.error("Could not rename the chat.");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    setBusy(true);
    try {
      await deleteThread(thread.id);
      deleted(thread.id);
      router.push("/chat");
    } catch (error) {
      toast.error(error instanceof ApiError && error.detail ? error.detail : "Could not delete the chat.");
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <ChatHeader>
        <form onSubmit={onRename} className="flex min-w-0 flex-1 items-center gap-2">
          <label htmlFor="chat-title" className="sr-only">
            Chat name
          </label>
          <Input
            id="chat-title"
            value={title}
            maxLength={TITLE_MAX}
            autoFocus
            readOnly={busy}
            onChange={(event) => setTitle(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") stopEditing();
            }}
          />
          <Button type="submit" variant="outline" disabled={busy || !title.trim()}>
            Save
          </Button>
          <Button type="button" variant="ghost" onClick={stopEditing}>
            Cancel
          </Button>
        </form>
      </ChatHeader>
    );
  }

  return (
    <ChatHeader>
      <h1 className="min-w-0 flex-1 truncate font-semibold tracking-tight">{threadTitle(thread)}</h1>
      <Button
        ref={renameButton}
        variant="ghost"
        size="icon"
        aria-label="Rename this chat"
        onClick={() => {
          setTitle(threadTitle(thread));
          setEditing(true);
        }}
      >
        <Pencil />
      </Button>
      <AlertDialog>
        <AlertDialogTrigger render={<Button variant="ghost" size="icon" aria-label="Delete this chat" disabled={answering || busy} />}>
          <Trash2 />
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this chat?</AlertDialogTitle>
            <AlertDialogDescription>“{threadTitle(thread)}” and all its messages are deleted. This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onDelete} disabled={busy}>
              {busy ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ChatHeader>
  );
}
```

The confirm button keeps the default variant, as the app's other confirmations do: the kit's `destructive` variant puts `#e11d48` on its own 10% tint, under 4.5:1. The API trims the title and stores it with `title_source = user`, so a later generated title never overwrites it.

- [ ] **Step 2: The thumbs**

Create `apps/web/src/components/chat/feedback-buttons.tsx`:

```tsx
"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import { Textarea } from "@/components/ui/textarea";
import { sendFeedback } from "@/lib/chat-api";

type Value = "up" | "down";

const COMMENT_MAX = 1000; // FeedbackBody.comment (plan 4a, Task 12)

/** Thumbs on an answer (spec 8 and 11): up is sent at once; down asks for an optional comment
 * first, so one request carries both. The answer's trace in Langfuse gets the score. */
export function FeedbackButtons({ messageId, value, onSaved }: { messageId: string; value: Value | null; onSaved: (value: Value) => void }) {
  const [open, setOpen] = useState(false);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(next: Value, text?: string) {
    setBusy(true);
    try {
      await sendFeedback(messageId, next, text || undefined);
      onSaved(next);
      setOpen(false);
      setComment("");
      toast.success("Thanks for the feedback");
    } catch {
      toast.error("Could not save the feedback.");
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void save("down", comment.trim());
  }

  return (
    <div role="group" aria-label="Rate this answer" className="flex gap-1">
      <Button variant="ghost" size="icon-sm" aria-label="Good answer" aria-pressed={value === "up"} disabled={busy} onClick={() => save("up")}>
        <ThumbsUp className={value === "up" ? "fill-current" : undefined} />
      </Button>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          render={<Button variant="ghost" size="icon-sm" aria-label="Bad answer" aria-pressed={value === "down"} disabled={busy} />}
        >
          <ThumbsDown className={value === "down" ? "fill-current" : undefined} />
        </PopoverTrigger>
        <PopoverContent align="start" className="w-80">
          <form onSubmit={onSubmit} className="flex flex-col gap-2">
            <PopoverTitle render={<label htmlFor={`feedback-${messageId}`} />}>What was wrong? (optional)</PopoverTitle>
            <Textarea
              id={`feedback-${messageId}`}
              value={comment}
              maxLength={COMMENT_MAX}
              placeholder="A wrong number, a missed note…"
              onChange={(event) => setComment(event.target.value)}
            />
            <Button type="submit" size="sm" className="self-end" disabled={busy}>
              Send
            </Button>
          </form>
        </PopoverContent>
      </Popover>
    </div>
  );
}
```

The popover's title is the field's label, and the popover is named by it.

- [ ] **Step 3: Thumbs under an answer**

Replace `apps/web/src/components/chat/chat-message.tsx` with:

```tsx
"use client";

import { Streamdown } from "streamdown";

import { answerBlocks, type ChatUIMessage } from "@/lib/chat";

import { FeedbackButtons } from "./feedback-buttons";
import { QueryDisclosure } from "./query-disclosure";

type Props = {
  message: ChatUIMessage;
  /** The answer that is streaming now: its markdown is still incomplete. */
  live: boolean;
  onFeedback: (messageId: string, value: "up" | "down") => void;
};

/** One message: the user's question as a bubble, or an answer as markdown with its queries. */
export function ChatMessageView({ message, live, onFeedback }: Props) {
  if (message.role === "user") {
    const text = message.parts.map((part) => (part.type === "text" ? part.text : "")).join("");
    return <div className="ml-auto max-w-[85%] rounded-2xl bg-card px-4 py-2.5 whitespace-pre-wrap wrap-anywhere">{text}</div>;
  }
  const meta = message.metadata;
  return (
    <article aria-label="Answer" className="flex min-w-0 flex-col gap-3">
      {answerBlocks(message.parts).map((block, index) =>
        block.kind === "queries" ? (
          <QueryDisclosure key={index} queries={block.queries} />
        ) : (
          <Streamdown
            key={index}
            isAnimating={live && block.streaming}
            controls={false}
            // Headings stay small: an answer's "How I counted it" is a note, not a page title.
            className="[&_:is(h1,h2,h3,h4)]:mt-4 [&_:is(h1,h2,h3,h4)]:text-base"
          >
            {block.text}
          </Streamdown>
        ),
      )}
      {meta?.status === "stopped" ? <p className="text-sm text-muted-foreground">You stopped this answer.</p> : null}
      {meta?.status === "error" ? <p className="text-sm text-muted-foreground">This answer did not finish.</p> : null}
      {meta?.status === "ok" ? (
        <FeedbackButtons messageId={message.id} value={meta.feedback} onSaved={(value) => onFeedback(message.id, value)} />
      ) : null}
    </article>
  );
}
```

A live answer has no `metadata` until its stream ends (the provider's `onFinish`), so its thumbs appear only once the API has saved it.

- [ ] **Step 4: The conversation with the title row and the thumbs**

Replace `apps/web/src/components/chat/conversation.tsx` with:

```tsx
"use client";

import { useChat } from "@ai-sdk/react";
import { ArrowDown } from "lucide-react";
import { useEffect, useState } from "react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";

import { Button } from "@/components/ui/button";
import { chatErrorText, isThinking, unanswered, type ChatMessage } from "@/lib/chat";

import { ChatHeader } from "./chat-header";
import { ChatMessageView } from "./chat-message";
import { useChats } from "./chats-provider";
import { Composer } from "./composer";
import { ThreadHeader } from "./thread-header";

/** One chat: its history, the streaming answer, and the question box (spec 10). */
export function Conversation({ threadId, history }: { threadId: string; history: ChatMessage[] }) {
  const { threads, chatFor } = useChats();
  const [chat] = useState(() => chatFor(threadId, history));
  const { messages, status, error, sendMessage, stop, setMessages } = useChat({ chat });
  const [draft, setDraft] = useState("");
  const answering = status === "submitted" || status === "streaming";
  const thread = threads.find((t) => t.id === threadId);
  const last = messages.at(-1);
  const thinking = answering && isThinking(messages);

  useEffect(() => {
    // A new chat arrives here from /chat while it answers; the box it was asked from is gone.
    const answeringOnArrival = chat.status === "submitted" || chat.status === "streaming";
    if (answeringOnArrival && document.activeElement === document.body) document.getElementById("chat-question")?.focus();
  }, [chat]);

  async function send(text: string) {
    setDraft("");
    await sendMessage({ text });
    // A question the API refused or never got goes back to the box, to send again.
    const question = chat.status === "error" ? unanswered(chat.messages) : null;
    if (question !== null) {
      setMessages(chat.messages.slice(0, -1));
      setDraft(question);
    }
  }

  function saveFeedback(messageId: string, value: "up" | "down") {
    setMessages((all) =>
      all.map((m) => (m.id === messageId && m.metadata ? { ...m, metadata: { ...m.metadata, feedback: value } } : m)),
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      {thread ? (
        <ThreadHeader thread={thread} answering={answering} />
      ) : (
        <ChatHeader>
          <h1 className="min-w-0 flex-1 truncate font-semibold tracking-tight">Chat</h1>
        </ChatHeader>
      )}
      <StickToBottom
        className="relative min-h-0 flex-1 rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        initial="instant"
        resize="smooth"
        role="log"
        aria-label="Conversation"
        aria-busy={answering}
        tabIndex={-1}
      >
        <StickToBottom.Content className="mx-auto flex w-full max-w-3xl flex-col gap-6 py-2">
          {messages.map((message) => (
            <ChatMessageView key={message.id} message={message} live={answering && message === last} onFeedback={saveFeedback} />
          ))}
          {thinking ? <p className="shimmer text-sm">Thinking…</p> : null}
          {error ? (
            <p role="alert" className="rounded-xl bg-card px-4 py-3 text-sm text-bad">
              {chatErrorText(error)}
            </p>
          ) : null}
        </StickToBottom.Content>
        <ScrollToLatest />
      </StickToBottom>
      <div className="mx-auto w-full max-w-3xl">
        <Composer value={draft} onChange={setDraft} onSend={send} answering={answering} onStop={() => void stop()} />
      </div>
    </div>
  );
}

function ScrollToLatest() {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();
  if (isAtBottom) return null;
  return (
    <Button
      variant="outline"
      size="icon"
      aria-label="Scroll to the latest message"
      className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full shadow-sm"
      onClick={(event) => {
        // The button disappears once the view is at the bottom: focus moves to the conversation
        // first, so it never drops to the page.
        event.currentTarget.closest<HTMLElement>("[role=log]")?.focus({ preventScroll: true });
        void scrollToBottom();
      }}
    >
      <ArrowDown />
    </Button>
  );
}
```

A chat missing from the list (opened by URL after another tab deleted it) keeps a plain "Chat" heading without actions.

- [ ] **Step 5: Run the gate**

Run: `cd apps/web && npm run lint && npx next typegen && npx tsc --noEmit && npm test && npm run build`
Expected: no errors.

- [ ] **Step 6: Check it in the browser (R3)**

Set up R3. With the session `slice4b-scratch`, start a chat from `/chat` with `how much in total`, wait for "How I counted it", then:

1. Thumbs: under the answer, "Good answer" and "Bad answer" in a group "Rate this answer". Click Good answer: a toast "Thanks for the feedback" and `aria-pressed="true"` on it. Click Bad answer: a popover with the field "What was wrong? (optional)"; type `The total misses a refund`, click Send: the toast, Bad answer pressed, Good answer not. Reload: Bad answer still pressed. The database agrees: `PGPASSWORD=postgres psql -h 127.0.0.1 -p 54322 -U postgres scratch_review -tAc "select feedback from chat_messages where role = 'assistant' order by created_at desc limit 1"` prints `down`.
2. No thumbs under a stopped or failed answer: ask `please fail`: "This answer did not finish." and no "Rate this answer" group under it.
3. Rename: click "Rename this chat": a field "Chat name" holding the title, focused. Press Escape: the title is back and `eval "document.activeElement.getAttribute('aria-label')"` is `"Rename this chat"`. Rename again to `January spending`, press Enter: the h1 and the list show it, the chat keeps its place in the list, and focus is on Rename again. Reload: the name stays.
4. Delete: ask `slow please`; while it streams, "Delete this chat" is disabled. Stop it. Click Delete this chat: a dialog "Delete this chat?" quoting “January spending”; Cancel closes it. Open it again and click Delete: `/chat`, and the chat is gone from the list. `open` its old URL: the 404 page.
5. Screenshot `task6-feedback.png`. `errors` (none), `close`. Finish R3.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/chat
git commit -m "feat: rename, delete and rate chats"
```

---

### Task 7: Final checks, docs and a live run with Raul

**Files:**
- Modify: `CLAUDE.md`, `README.md`; whatever files the reviews below fix
- Create (git-ignored, never committed): `dogfood-output/slice-4b/report.md`

- [ ] **Step 1: A core check of every chat flow (R3)**

On a fresh R3 (a new scratch copy, the final build), load `agent-browser skills get core` and run, in the session `slice4b-scratch`: a new chat from an example and from the box; the streamed answer with "Thinking…", "Running a query…" and the live title; the query disclosure (two queries, a failed query, `big` cut at 200); Stop, then reload (stopped kept) and a next question; a stream error (`fail`); a 409 (the curl of Task 4, Step 7); reload keeps the history and the thumbs; rename; delete; leaving and returning mid-answer; the 503 state (`--disabled`) and the API stopped; a 480 px tall window; a 390 px phone with the chats sheet. Each must behave as its task's check says. Record anything that does not.

- [ ] **Step 2: One dogfood pass over the whole app**

Load `agent-browser skills get dogfood` and follow it with the session `slice4b-dogfood`: real data on :3000, read-only (R1), for every page — `/`, a group, a category, a merchant, `/income`, `/transactions` (filters and the side panel, opened and cancelled), `/subscriptions`, `/review`, `/imports`, `/settings`, and `/chat` (open the existing chats, if any; send nothing: it would call xAI) — at 1280 px and at 390 px; then the chat's write flows on R3 (Step 1's list). Write the report to `dogfood-output/slice-4b/report.md`, with screenshots beside it (absolute paths). Use generic issue titles; the report stays git-ignored.

- [ ] **Step 3: The web design guidelines review**

Load the `web-design-guidelines` skill and run it on the files this slice changed:

```bash
git diff --name-only main...HEAD -- apps/web/src | grep -E '\.tsx$'
```

Fix every finding that breaks accessibility (names, focus, contrast), the 390 px layout or the copy rules. Record the ones left as they are, with a reason, in the report.

- [ ] **Step 4: Fix what the passes found**

One `fix:` commit per issue (or per group of issues in one file), each followed by the check of the task that owns the file. Then run the gate:

Run: `cd apps/web && npm run lint && npx next typegen && npx tsc --noEmit && npm test && npm run build`
Expected: no errors.

- [ ] **Step 5: The docs**

In `CLAUDE.md`, section "Verifying the web app", replace the sentence that starts "Run the API and web first; pages live at" with:

```markdown
Run the API and web first; pages live at `http://localhost:3000` (`/`, `/spending/<group>`,
`/income`, `/merchants/<id>`, `/transactions`, `/subscriptions`, `/chat`, `/chat/<id>`, `/review`,
`/imports`, `/settings`).
```

and add, at the end of that section:

```markdown
- Chat checks run on scripted models, never on paid ones: the API from
  `apps/api/tests/scripted_chat_server.py` on a scratch copy of the database, recipe "R3" in
  `docs/superpowers/plans/2026-10-12-slice-4b-chat-web.md`.
```

In `README.md`, section "Status", change the sentence about slice 4 (plan 4a's Task 14 wrote "slice 4a … complete; the `/chat` page comes next (4b)") so it says that slice 4, the chat agent (the API, `finance chat` and the `/chat` page), is complete. In the section "How the chat agent answers" (plan 4a, Task 14), add one paragraph: the web chat streams answers with the AI SDK's `useChat` straight from the API, shows the queries behind each answer, and keeps every chat (rename, delete, thumbs).

```bash
git status --short dogfood-output   # expected: nothing (the folder is git-ignored)
git add CLAUDE.md README.md
git commit -m "docs: the chat page in the project instructions and the README"
```

- [ ] **Step 6: A live run with Raul (paid model calls)**

Ask Raul before starting: this spends xAI credit (a few cents per question) and uses his real data. Nothing from it is committed.

1. Start the real API (`cd apps/api && uv run task api`, no `chat disabled` line in its log) and the web (`cd apps/web && npm run dev`).
2. Raul asks three to five questions on `/chat` (for example a total for last month, a merchant by an approximate name, a comparison of two months, and a follow-up in the same chat), and stops one long answer.
3. Check with him: "Thinking…" covers the model's reasoning time; the queries appear in the disclosure as they run; the answer reads well (the key number first, a table when the data is tabular, a small "How I counted it" in the question's language); the title arrives in the question's language; the numbers match the dashboards; the stopped answer is kept after a reload; thumbs (with a comment) reach Langfuse as a `user-feedback` score on the answer's trace, and the stopped turn's trace has `stopped = 1`.
4. Write the findings for Raul in the chat, not in the repo. Prompt or semantic-layer changes go through their own small change with his approval. He decides whether to delete the test chats from `/chat`.

- [ ] **Step 7: Clean up**

Stop the processes, drop `scratch_review` (R3 step 5), and confirm `git status` is clean apart from the git-ignored `dogfood-output/`.

Expected: the spec's slice 4 "done" list for the web holds: `/chat` passed an `agent-browser` core check, one dogfood pass covers the app, and lint, types, build and unit tests are green.

---

## Notes for the executor

- **Order:** Before Task 1 → Task 0 → Tasks 1 to 7. Task 2 must come before Task 3 (every browser check uses its server). Tasks 3 to 6 each leave a working app: `/chat` itself and the "Chat" navigation entry arrive in Task 5, so Tasks 3 and 4 are checked on chats created with curl.
- **Known gaps, accepted:** a chat continued in another tab or in `finance chat` shows those turns only after a reload; P3 (the title of a stopped first turn appears after a reload); P4 (one `user-feedback` score per click); the database-down notice (`INFRA_MESSAGE`) streams as a normal answer with thumbs, while the history stores it as `error` and shows "This answer did not finish." after a reload.
- **Not in this plan:** resuming an answer after a reload (the reload stops it, which saves it as stopped), editing or regenerating a question, charts in the chat, AI Elements (spec 10), shadcn's `message-scroller` (Decision F), dark mode, Playwright tests (v2).
