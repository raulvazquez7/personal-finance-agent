"""Assemble the chat agent: one ReAct loop, the run_sql tool and the middleware stack."""

from dataclasses import dataclass

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer

from finance.agent.middleware import build_middleware
from finance.settings import ChatSettings


@dataclass(frozen=True)
class AgentContext:
    """Per-turn runtime context (create_agent's context_schema); never stored in the checkpoint."""

    data_context: str


@dataclass(frozen=True)
class ChatModels:
    agent: BaseChatModel
    summary: BaseChatModel
    title: BaseChatModel


def chat_models(chat: ChatSettings) -> ChatModels:
    """`reasoning_effort` is passed to providers that accept it (xAI, OpenAI)."""
    return ChatModels(
        agent=init_chat_model(
            chat.model, reasoning_effort=chat.reasoning_effort, max_retries=chat.max_retries
        ),
        summary=init_chat_model(
            chat.summary_model,
            reasoning_effort=chat.summary_reasoning_effort,
            max_retries=chat.max_retries,
        ),
        title=init_chat_model(chat.title_model, max_retries=chat.max_retries),
    )


def build_agent(
    models: ChatModels, tools: list[BaseTool], chat: ChatSettings, checkpointer: Checkpointer
):
    return create_agent(
        models.agent,
        tools=tools,
        middleware=build_middleware(chat, models.summary),
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )
