import { APICallError, type UIMessage } from "ai";

import { ApiError, type Schemas } from "@/lib/api";

export type Thread = Schemas["Thread"];
export type ChatMessage = Schemas["ChatMessage"];
export type QueryResult = Schemas["QueryResult"];

/** How an answer ended, and the user's thumbs. The history carries it; a live answer gets it
 * when its stream ends. */
export type AnswerMeta = { status: ChatMessage["status"]; feedback: ChatMessage["feedback"] };

/** `run_sql`'s output is a QueryResult, or only `{error}` when the per-turn query limit refused
 * the call (ui_parts in apps/api/finance/agent/ui_stream.py). */
export type QueryOutput = QueryResult | { error: string };

/** The messages useChat holds: the API's stream parts (ui_parts in apps/api/finance/agent/ui_stream.py)
 * typed for this app. */
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
 * `error` part (ERROR_TEXT in apps/api/finance/agent/service.py) and the 409 detail. */
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
