import asyncio
from dataclasses import dataclass

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from psycopg_pool import PoolTimeout

from finance.agent import runtime, store
from finance.agent.graph import ChatModels
from finance.agent.middleware import INFRA_MESSAGE
from finance.agent.models import QueryResult
from finance.agent.runtime import open_chat
from finance.agent.service import ERROR_TEXT, ThreadBusy
from finance.settings import get_settings
from tests.fakes import HoldingChatModel, ScriptedChatModel, scripted_models, title_call, tool_call

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


def test_a_stopped_answer_is_saved_as_stopped_and_the_thread_keeps_working():
    agent = HoldingChatModel(
        hold="late",
        responses=[tool_call("SELECT 1 AS n", "c1"), AIMessage("late"), AIMessage("Next answer.")],
    )
    models = ChatModels(
        agent=agent, summary=agent, title=ScriptedChatModel(responses=[title_call("t")])
    )

    async def body(chat, thread):
        parts = chat.stream_turn(thread, "slow question")
        async for part in parts:
            if part["type"] == "tool-output-available":
                break
        await asyncio.to_thread(agent.started.wait, 5)  # the answer is being written
        await parts.aclose()  # what a client disconnect does
        agent.release.set()
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


def test_a_thread_being_deleted_refuses_a_new_turn(monkeypatch):
    """A send that arrives while the delete awaits the database must not start a turn whose
    checkpoint the delete then removes."""
    held, release = asyncio.Event(), asyncio.Event()
    delete_rows = store.delete_thread

    async def slow_delete(pool, thread_id):
        held.set()
        await release.wait()
        return await delete_rows(pool, thread_id)

    monkeypatch.setattr(store, "delete_thread", slow_delete)

    async def body(chat, thread):
        deleting = asyncio.create_task(chat.delete_thread(thread.id))
        await held.wait()
        try:
            with pytest.raises(ThreadBusy):
                chat.stream_turn(thread, "hello")
        finally:
            release.set()
            deleted = await deleting
        return deleted, thread.id in chat.active

    assert _scenario(scripted_models([AIMessage("Hi.")]), body) == (True, False)


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


def test_a_database_outage_ends_the_turn_saves_it_as_error_and_the_thread_keeps_working(
    monkeypatch,
):
    real_run_query = runtime.run_query
    outages = []

    async def run_query_after_an_outage(pool, sql, **limits):
        if not outages:
            outages.append(sql)
            return QueryResult(sql=sql, error="connection refused", infra_error=True)
        return await real_run_query(pool, sql, **limits)

    # open_chat binds run_query into the run_sql tool when it opens: patch it before that.
    monkeypatch.setattr(runtime, "run_query", run_query_after_an_outage)
    # The outage ends the first turn before a second model call, so "Back again." answers
    # the second turn.
    models = scripted_models([tool_call("SELECT 1 AS n", "c1"), AIMessage("Back again.")])

    async def body(chat, thread):
        first = await _collect(chat.stream_turn(thread, "first question"))
        refreshed = await store.get_thread(chat.pool, thread.id)
        await _collect(chat.stream_turn(refreshed, "second question"))
        return first, thread.id in chat.active, await store.list_messages(chat.pool, thread.id)

    first, busy, messages = _scenario(models, body)
    deltas = "".join(p["delta"] for p in first if p["type"] == "text-delta")
    assert INFRA_MESSAGE in deltas and first[-1]["type"] == "finish"
    assert [(m.role, m.status) for m in messages] == [
        ("user", "ok"),
        ("assistant", "error"),
        ("user", "ok"),
        ("assistant", "ok"),
    ]
    assert messages[1].queries[0].infra_error
    assert messages[3].content == "Back again."
    assert not busy


def test_a_database_outage_before_the_agent_answers_with_the_fixed_message(monkeypatch):
    """Saving the question is the first database call of a turn: when the pool has no
    connection to give, the turn ends with the outage message, not the generic error."""
    add_message = store.add_message
    calls = []

    async def add_message_after_an_outage(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise PoolTimeout("couldn't get a connection after 5.00 sec")
        return await add_message(*args, **kwargs)

    monkeypatch.setattr(store, "add_message", add_message_after_an_outage)

    async def body(chat, thread):
        first = await _collect(chat.stream_turn(thread, "first question"))
        busy = thread.id in chat.active
        await _collect(chat.stream_turn(thread, "second question"))
        return first, busy, chat.pool.timeout, await store.list_messages(chat.pool, thread.id)

    first, busy, pool_timeout, messages = _scenario(scripted_models([AIMessage("Back.")]), body)
    assert {"type": "error", "errorText": INFRA_MESSAGE} in first and first[-1]["type"] == "finish"
    assert not busy
    assert pool_timeout == get_settings().chat.pool_timeout_seconds
    assert [(m.role, m.status) for m in messages] == [
        ("assistant", "error"),
        ("user", "ok"),
        ("assistant", "ok"),
    ]
    assert messages[-1].content == "Back."


@dataclass
class Unexpected:
    """A type no checkpoint of ours holds: strict loading must not revive it."""

    value: int


def test_checkpoints_load_only_allowlisted_types():
    async def go():
        async with open_chat(get_settings(), scripted_models([])) as chat:
            serde = chat.checkpointer.serde
            state = {
                "messages": [
                    AIMessage("Hi."),
                    ToolMessage("rows: 1", tool_call_id="c1", artifact={"sql": "SELECT 1"}),
                ],
                "other": Unexpected(1),
            }
            return serde.loads_typed(serde.dumps_typed(state))

    loaded = asyncio.run(go())
    assert loaded["messages"][0] == AIMessage("Hi.")
    assert loaded["messages"][1].artifact == {"sql": "SELECT 1"}
    assert loaded["other"] == {"value": 1}  # blocked: the raw fields, not an Unexpected
