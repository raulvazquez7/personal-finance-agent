import asyncio
from uuid import UUID

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
    thread_id = UUID(output.splitlines()[0].removeprefix("chat "))

    async def cleanup():
        async with open_chat(get_settings(), scripted_models([])) as chat:
            messages = await store.list_messages(chat.pool, thread_id)
            await chat.delete_thread(thread_id)
            return messages

    messages = []
    try:
        assert code == 0 and "[query]\nSELECT 1 AS n" in output and "One." in output
    finally:
        messages = asyncio.run(cleanup())  # always delete the thread, even if the check fails
    assert [m.role for m in messages] == ["user", "assistant"]
