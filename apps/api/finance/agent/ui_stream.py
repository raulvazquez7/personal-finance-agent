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

from finance.agent.middleware import LIMIT_MESSAGE, NOTICE_NODES
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
    database_unreachable: bool = False  # the turn itself could not reach the database

    @property
    def text(self) -> str:
        return "\n\n".join(t for t in self.texts if t)

    @property
    def infra_error(self) -> bool:
        return self.database_unreachable or any(q.infra_error for q in self.queries)


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
            # The limit notice arrives whole, once (a node's output, not a model stream); the
            # user reads our sentence, the checkpoint keeps LangChain's for the model.
            text = LIMIT_MESSAGE if node == "ModelCallLimitMiddleware.before_model" else chunk.text
            if text_id is None:
                text_id = f"text-{len(record.texts)}"
                record.texts.append("")
                yield {"type": "text-start", "id": text_id}
            record.texts[-1] += text
            yield {"type": "text-delta", "id": text_id, "delta": text}
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
