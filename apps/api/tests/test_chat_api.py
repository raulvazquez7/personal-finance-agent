import asyncio
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from finance.agent import store
from finance.agent.graph import ChatModels
from finance.agent.runtime import open_chat
from finance.api import chat as chat_api
from finance.api.main import app
from finance.settings import get_settings
from tests.fakes import HoldingChatModel, ScriptedChatModel, scripted_models, title_call, tool_call


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


def test_feedback_sends_one_langfuse_score_per_answer(monkeypatch):
    message_id = uuid4()
    scores = []

    async def set_feedback(pool, message, value):
        assert (message, value) == (message_id, "down")
        return "trace-1"

    monkeypatch.setattr(chat_api.store, "set_feedback", set_feedback)
    monkeypatch.setattr(
        chat_api, "langfuse", lambda: SimpleNamespace(create_score=lambda **k: scores.append(k))
    )
    previous = getattr(app.state, "chat", None)
    app.state.chat = SimpleNamespace(pool=None)
    try:
        response = TestClient(app).post(
            f"/chat/messages/{message_id}/feedback", json={"value": "down", "comment": "Wrong."}
        )
    finally:
        app.state.chat = previous
    assert response.status_code == 204
    assert scores == [
        {
            "trace_id": "trace-1",
            "score_id": f"{message_id}-feedback",
            "name": "user-feedback",
            "value": 0.0,
            "data_type": "BOOLEAN",
            "comment": "Wrong.",
        }
    ]


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
        "transient": True,
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
        return thread, renamed.json(), deleted.status_code, missing.status_code

    thread, renamed, deleted, missing = _run(scripted_models([]), body)
    assert (renamed["title"], renamed["title_source"]) == ("Trips", "user")
    assert renamed["updated_at"] == thread["updated_at"]  # renaming is not activity
    assert (deleted, missing) == (204, 404)


@pytest.mark.integration
def test_a_blank_title_or_message_is_422():
    async def body(client, chat, new_thread):
        thread = await new_thread()
        renamed = await client.patch(f"/chat/threads/{thread['id']}", json={"title": "   "})
        sent = await client.post(f"/chat/threads/{thread['id']}/messages", json={"text": "   "})
        history = (await client.get(f"/chat/threads/{thread['id']}/messages")).json()
        return renamed.status_code, sent.status_code, history

    assert _run(scripted_models([]), body) == (422, 422, [])


@pytest.mark.integration
def test_a_title_the_user_sets_is_kept_after_the_first_message():
    models = scripted_models([AIMessage("Hello.")], title="Generated title")

    async def body(client, chat, new_thread):
        thread = await new_thread()
        await client.patch(f"/chat/threads/{thread['id']}", json={"title": "My trips"})
        response = await client.post(f"/chat/threads/{thread['id']}/messages", json={"text": "hi"})
        threads = (await client.get("/chat/threads")).json()
        return _events(response.text), next(t for t in threads if t["id"] == thread["id"])

    events, thread = _run(models, body)
    assert (thread["title"], thread["title_source"]) == ("My trips", "user")
    assert events[-2:] == [{"type": "finish"}, "[DONE]"]
    assert not [e for e in events if e != "[DONE]" and e["type"] == "data-title"]


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


@pytest.mark.integration
def test_a_request_closed_mid_answer_saves_the_stopped_answer_over_real_http():
    """The browser's Stop aborts the request; the server then cancels the response while it waits
    for the turn, and that must not cancel the turn's save too. Only real HTTP shows this."""
    agent = HoldingChatModel(
        hold="late",
        responses=[tool_call("SELECT 1 AS n", "c1"), AIMessage("late"), AIMessage("Next.")],
    )
    models = ChatModels(
        agent=agent, summary=agent, title=ScriptedChatModel(responses=[title_call("t")])
    )

    async def go():
        async with open_chat(get_settings(), models) as chat:
            previous = getattr(app.state, "chat", None)
            app.state.chat = chat
            server = uvicorn.Server(
                uvicorn.Config(app, host="127.0.0.1", port=0, lifespan="off", log_level="warning")
            )
            serving = asyncio.create_task(server.serve())
            while not server.started:
                await asyncio.sleep(0.01)
            port = server.servers[0].sockets[0].getsockname()[1]
            thread = await store.create_thread(chat.pool)
            try:
                async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
                    url = f"/chat/threads/{thread.id}/messages"
                    async with client.stream("POST", url, json={"text": "slow"}) as response:
                        async for line in response.aiter_lines():
                            if "tool-output-available" in line:
                                break
                        await asyncio.to_thread(agent.started.wait, 5)
                    # leaving the block closes the connection: what the browser's Stop does
                for _ in range(100):
                    if thread.id not in chat.active:
                        break
                    await asyncio.sleep(0.05)
                agent.release.set()
                return await store.list_messages(chat.pool, thread.id)
            finally:
                app.state.chat = previous
                server.should_exit = True
                await serving
                await chat.delete_thread(thread.id)

    messages = asyncio.run(go())
    assert [(m.role, m.status) for m in messages] == [("user", "ok"), ("assistant", "stopped")]
