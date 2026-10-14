import asyncio

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from finance.agent.graph import AgentContext, ChatModels, build_agent
from finance.agent.middleware import INFRA_MESSAGE, LIMIT_MESSAGE
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


def test_the_model_call_limit_notice_reaches_the_user():
    calls = [tool_call(f"SELECT {n}", f"c{n}") for n in range(3)]
    parts, record = _parts(calls, max_sql_calls_per_turn=1, max_model_calls_per_turn=2)
    assert parts[-1]["type"] == "text-end"
    assert record.texts[-1] == LIMIT_MESSAGE
    deltas = [p["delta"] for p in parts if p["type"] == "text-delta"]
    assert deltas[-1] == LIMIT_MESSAGE


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
