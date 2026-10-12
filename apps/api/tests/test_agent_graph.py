import asyncio
from hashlib import sha256

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from finance.agent.graph import AgentContext, ChatModels, build_agent
from finance.agent.middleware import CANCELLED, CLEARED, INFRA_MESSAGE, NOTICE_NODES
from finance.agent.models import QueryResult
from finance.agent.prompt import INSTRUCTIONS, PROMPT_VERSION, SUMMARY_PROMPT
from finance.agent.tools import make_run_sql
from finance.settings import ChatSettings
from tests.fakes import ScriptedChatModel, tool_call

CONFIG = {"configurable": {"thread_id": "t1"}}
CONTEXT = AgentContext(data_context="DATA CONTEXT")


def _agent(model, run_query=None, **chat):
    async def ok(sql):
        return QueryResult(sql=sql, columns=["n"], rows=[["1"]], row_count=1)

    tool = make_run_sql(run_query or ok, rows_shown=50, max_chars=8000)
    models = ChatModels(agent=model, summary=model, title=model)
    return build_agent(models, [tool], ChatSettings(**chat), InMemorySaver())


def _ask(agent, text, config=CONFIG):
    return asyncio.run(agent.ainvoke({"messages": [HumanMessage(text)]}, config, context=CONTEXT))


def test_one_query_then_an_answer_with_instructions_and_data_context_as_system_blocks():
    model = ScriptedChatModel(responses=[tool_call("SELECT 1", "c1"), AIMessage("One.")])
    agent = _agent(model)
    result = _ask(agent, "how many?")
    system = model.calls[0][0]
    assert isinstance(system, SystemMessage)
    assert [block["text"] for block in system.content] == [INSTRUCTIONS, "DATA CONTEXT"]
    types = [type(m).__name__ for m in result["messages"]]
    assert types == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]
    assert result["messages"][2].content == "rows: 1\nn\n1"
    assert result["messages"][-1].content == "One."


def test_a_tool_call_left_unanswered_is_closed_before_the_next_turn():
    model = ScriptedChatModel(responses=[AIMessage("Fine.")])
    agent = _agent(model)
    dangling = [HumanMessage("q1"), tool_call("SELECT 1", "c1")]
    asyncio.run(agent.aupdate_state(CONFIG, {"messages": dangling}))
    _ask(agent, "q2")
    seen = model.calls[0][1:]  # after the system message
    assert [type(m).__name__ for m in seen] == [
        "HumanMessage",
        "AIMessage",
        "ToolMessage",
        "HumanMessage",
    ]
    assert seen[2].content == CANCELLED and seen[2].tool_call_id == "c1"


def test_an_unreachable_database_ends_the_turn_without_another_model_call():
    async def down(sql):
        return QueryResult(sql=sql, error="connection refused", infra_error=True)

    model = ScriptedChatModel(responses=[tool_call("SELECT 1", "c1"), AIMessage("never")])
    result = _ask(_agent(model, down), "q")
    assert len(model.calls) == 1
    assert result["messages"][-1].content == INFRA_MESSAGE


def test_after_the_query_limit_the_model_answers_with_what_it_has():
    calls = [tool_call(f"SELECT {n}", f"c{n}") for n in range(3)]
    model = ScriptedChatModel(responses=[*calls, AIMessage("Done.")])
    result = _ask(_agent(model, max_sql_calls_per_turn=2), "q")
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert "Do not call 'run_sql' again" in tool_messages[-1].content
    assert result["messages"][-1].content == "Done."


def test_old_query_results_leave_the_request_but_keep_their_sql():
    async def wide(sql):
        return QueryResult(sql=sql, columns=["t"], rows=[["x" * 3000]], row_count=1)

    calls = [tool_call(f"SELECT {n}", f"c{n}") for n in range(3)]
    model = ScriptedChatModel(responses=[*calls, AIMessage("Done.")])
    agent = _agent(model, wide, clear_tool_results_trigger_tokens=1000, clear_tool_results_keep=1)
    _ask(agent, "q")
    last_request = model.calls[-1]
    results = [m.content for m in last_request if isinstance(m, ToolMessage)]
    assert results[0] == CLEARED and results[-1].startswith("rows: 1")
    assert last_request[2].tool_calls[0]["args"]["sql"] == "SELECT 0"


def test_the_system_message_is_never_stored_in_the_thread():
    model = ScriptedChatModel(responses=[AIMessage("Hi.")])
    agent = _agent(model)
    _ask(agent, "hello")
    state = asyncio.run(agent.aget_state(CONFIG))
    assert not any(isinstance(m, SystemMessage) for m in state.values["messages"])


def test_the_query_limit_is_reached_before_the_recursion_backstop():
    chat = ChatSettings()
    calls = [tool_call(f"SELECT {n}", f"c{n}") for n in range(chat.max_sql_calls_per_turn)]
    model = ScriptedChatModel(responses=[*calls, AIMessage("All done.")])
    config = {"configurable": {"thread_id": "deep"}, "recursion_limit": chat.recursion_limit}
    result = _ask(_agent(model), "q", config)
    assert result["messages"][-1].content == "All done."


def test_the_prompt_version_changes_with_the_instructions_or_the_summary_prompt():
    both = sha256("\0".join([INSTRUCTIONS, SUMMARY_PROMPT]).encode()).hexdigest()[:12]
    assert PROMPT_VERSION == both


def test_the_nodes_whose_notices_reach_the_user_exist_in_the_agent():
    agent = _agent(ScriptedChatModel(responses=[]))
    assert NOTICE_NODES <= set(agent.get_graph().nodes)
