"""The agent's middleware stack (spec section 7.3): built-in limits and context management, plus
three small hooks of our own."""

from typing import Any

from langchain.agents.middleware import (
    AgentState,
    ClearToolUsesEdit,
    ContextEditingMiddleware,
    ModelCallLimitMiddleware,
    ModelRequest,
    SummarizationMiddleware,
    ToolCallLimitMiddleware,
    before_agent,
    before_model,
    dynamic_prompt,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, RemoveMessage, SystemMessage, ToolMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

from finance.agent.prompt import SUMMARY_PROMPT, system_message
from finance.settings import ChatSettings

INFRA_MESSAGE = "I can't reach your database right now. Try again in a moment."
# What the user reads when ModelCallLimitMiddleware ends a turn (its own text names the limit).
LIMIT_MESSAGE = (
    "I stopped before finishing: this question needed more steps than one answer allows. "
    "Try a narrower question."
)
CANCELLED = "Cancelled: the user stopped the answer before this query returned."
CLEARED = "[result cleared: run the query again if you need these numbers]"
# Middleware nodes whose AI messages the user must see (stream adapter).
NOTICE_NODES = frozenset(
    {"ModelCallLimitMiddleware.before_model", "stop_on_infra_error.before_model"}
)


@before_agent(name="close_dangling_tool_calls")
def close_dangling_tool_calls(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """A stopped turn can leave a tool call without its result, and model providers reject such
    a history. Answer each one with a cancellation right after its call (the idea of deepagents'
    PatchToolCallsMiddleware, not worth that dependency)."""
    messages = state["messages"]
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    patched, changed = [], False
    for message in messages:
        patched.append(message)
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                if call["id"] not in answered:
                    patched.append(
                        ToolMessage(CANCELLED, tool_call_id=call["id"], name=call["name"])
                    )
                    changed = True
    if not changed:
        return None
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *patched]}


@before_model(can_jump_to=["end"], name="stop_on_infra_error")
def stop_on_infra_error(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """When the database is unreachable, end the turn with a fixed message: another model call
    would not heal it, so the turn fails loudly."""
    for message in reversed(state["messages"]):
        if not isinstance(message, ToolMessage):
            break
        if isinstance(message.artifact, dict) and message.artifact.get("infra_error"):
            return {"messages": [AIMessage(INFRA_MESSAGE)], "jump_to": "end"}
    return None


@dynamic_prompt
def system_prompt(request: ModelRequest) -> SystemMessage:
    return system_message(request.runtime.context.data_context)


def build_middleware(chat: ChatSettings, summary_model: BaseChatModel) -> list:
    return [
        close_dangling_tool_calls,
        SummarizationMiddleware(
            model=summary_model,
            trigger=("tokens", chat.summary_trigger_tokens),
            keep=("messages", chat.summary_keep_messages),
            summary_prompt=SUMMARY_PROMPT,
            trim_tokens_to_summarize=None,  # the default 4,000 could drop the previous summary
        ),
        ContextEditingMiddleware(
            edits=[
                ClearToolUsesEdit(
                    trigger=chat.clear_tool_results_trigger_tokens,
                    keep=chat.clear_tool_results_keep,
                    placeholder=CLEARED,
                )
            ]
        ),
        ToolCallLimitMiddleware(
            tool_name="run_sql", run_limit=chat.max_sql_calls_per_turn, exit_behavior="continue"
        ),
        ModelCallLimitMiddleware(run_limit=chat.max_model_calls_per_turn, exit_behavior="end"),
        stop_on_infra_error,
        system_prompt,
    ]
