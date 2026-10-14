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

import psycopg
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from psycopg.conninfo import conninfo_to_dict

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


def is_scratch_database(url: str) -> bool:
    """Whether the database psycopg would open for this URL is a scratch copy."""
    try:
        name = conninfo_to_dict(url).get("dbname") or ""
    except psycopg.Error:
        return False
    return str(name).startswith("scratch_")


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
    if not is_scratch_database(args.db_url):
        sys.exit("Refusing a database whose name does not start with scratch_ (see recipe R3).")
    # Before finance is imported: the settings and the Langfuse client read these once.
    os.environ["SUPABASE_DB_URL"] = args.db_url
    os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
    asyncio.run(serve(args.port, args.disabled))
