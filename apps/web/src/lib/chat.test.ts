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
