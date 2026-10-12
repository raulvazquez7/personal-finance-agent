"""One chat turn end to end (spec sections 7-9 and 11): data context, agent stream, AI SDK parts,
title, persistence, Langfuse trace and scores.

The turn runs in its own task and hands parts over a queue. The Langfuse context opens and closes
inside that task, a stopped answer cancels only the task (its partial answer is saved as
`stopped`), and the thread is released even if the client never reads the stream.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID, uuid4

from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from psycopg_pool import AsyncConnectionPool

from finance.agent import store
from finance.agent.catalog import read_catalog
from finance.agent.data_context import render_data_context
from finance.agent.graph import AgentContext
from finance.agent.models import MessageStatus, Thread
from finance.agent.prompt import PROMPT_VERSION
from finance.agent.semantic_layer import SemanticLayer
from finance.agent.title import generate_title
from finance.agent.ui_stream import TurnRecord, ui_parts
from finance.settings import ChatSettings
from finance.tracing import langfuse

logger = logging.getLogger(__name__)

ERROR_TEXT = "Something went wrong while answering. Try again."
_DONE = object()


class ThreadBusy(Exception):
    pass


def turn_scores(record: TurnRecord, status: MessageStatus) -> dict[str, tuple[float, str]]:
    """Deterministic per-turn scores for Langfuse: (value, data type)."""
    return {
        "sql_calls": (float(len(record.queries)), "NUMERIC"),
        "sql_errors": (float(sum(1 for q in record.queries if q.error)), "NUMERIC"),
        "hit_sql_limit": (float(record.hit_sql_limit), "BOOLEAN"),
        "stopped": (float(status == "stopped"), "BOOLEAN"),
        "infra_error": (float(record.infra_error), "BOOLEAN"),
    }


@dataclass
class ChatService:
    pool: AsyncConnectionPool
    agent: CompiledStateGraph
    checkpointer: BaseCheckpointSaver
    layer: SemanticLayer
    columns: dict[str, dict[str, str]]
    layer_version: str
    title_model: Runnable
    chat: ChatSettings
    active: set[UUID] = field(default_factory=set)

    async def data_context(self, today: date | None = None) -> str:
        catalog = await read_catalog(self.pool)
        return render_data_context(self.layer, self.columns, catalog, today or date.today())

    def stream_turn(self, thread: Thread, text: str) -> AsyncIterator[dict]:
        """Start the turn now and return its UI parts. A thread answers one turn at a time."""
        if thread.id in self.active:
            raise ThreadBusy(thread.id)
        self.active.add(thread.id)
        queue: asyncio.Queue = asyncio.Queue()
        message_id = uuid4()
        task = asyncio.create_task(self._turn(thread, text, message_id, queue))
        return self._relay(task, queue, message_id)

    async def delete_thread(self, thread_id: UUID) -> bool:
        if thread_id in self.active:
            raise ThreadBusy(thread_id)
        self.active.add(thread_id)  # a send during the delete gets ThreadBusy, not a new turn
        try:
            deleted = await store.delete_thread(self.pool, thread_id)
            await self.checkpointer.adelete_thread(str(thread_id))
        finally:
            self.active.discard(thread_id)
        return deleted

    async def _relay(
        self, task: asyncio.Task, queue: asyncio.Queue, message_id: UUID
    ) -> AsyncIterator[dict]:
        try:
            yield {"type": "start", "messageId": str(message_id)}
            while (part := await queue.get()) is not _DONE:
                yield part
            yield {"type": "finish"}
        finally:  # the client left or stopped: cancel the turn, which saves it as stopped
            if not task.done():
                task.cancel()
            # The server cancels this generator when the client leaves; shield the wait so that
            # cancellation does not reach the turn a second time, inside its save.
            await asyncio.shield(asyncio.gather(task, return_exceptions=True))

    async def _turn(
        self, thread: Thread, text: str, message_id: UUID, queue: asyncio.Queue
    ) -> None:
        record, status, trace_id = TurnRecord(), "ok", None
        attributes = {
            "session_id": str(thread.id),
            "user_id": self.chat.user_id,
            "tags": ["chat"],
            "version": PROMPT_VERSION,
            "trace_name": "chat-turn",
            "metadata": {
                "semantic_layer": self.layer_version,
                "model": self.chat.model,
                "reasoning_effort": self.chat.reasoning_effort,
            },
        }
        try:
            with (
                propagate_attributes(**attributes),
                langfuse().start_as_current_observation(
                    as_type="agent", name="chat-turn", input=text
                ) as turn,
            ):
                trace_id = turn.trace_id
                try:
                    await store.add_message(self.pool, thread.id, "user", text)
                    title = None
                    if thread.title_source is None:
                        title = asyncio.create_task(self._title(thread, text, queue))
                    await self._answer(thread, text, record, queue)
                    if title is not None:
                        await title
                except asyncio.CancelledError:
                    status = "stopped"
                    raise
                except Exception:
                    status = "error"
                    logger.exception("chat turn failed")
                    await queue.put({"type": "error", "errorText": ERROR_TEXT})
                finally:
                    if status == "ok" and record.infra_error:
                        status = "error"
                    level = "ERROR" if status == "error" else "DEFAULT"
                    if level == "DEFAULT" and record.hit_sql_limit:
                        level = "WARNING"  # the model answered, with what it had
                    turn.update(output=record.text, level=level, status_message=status)
        finally:
            try:
                await self._save(thread.id, message_id, record, status, trace_id)
            except Exception:
                logger.exception("could not save the chat answer")
            finally:
                self.active.discard(thread.id)
                queue.put_nowait(_DONE)

    async def _answer(
        self, thread: Thread, text: str, record: TurnRecord, queue: asyncio.Queue
    ) -> None:
        context = AgentContext(data_context=await self.data_context())
        config = {
            "configurable": {"thread_id": str(thread.id)},
            "recursion_limit": self.chat.recursion_limit,
            "callbacks": [CallbackHandler()],
        }
        stream = self.agent.astream(
            {"messages": [HumanMessage(text)]},
            config,
            context=context,
            stream_mode=["messages", "updates"],
            version="v2",
        )
        async for part in ui_parts(stream, record):
            await queue.put(part)

    async def _title(self, thread: Thread, text: str, queue: asyncio.Queue) -> None:
        config = {"callbacks": [CallbackHandler()], "run_name": "chat-title"}
        title, source = await generate_title(
            self.title_model, text, self.chat.title_max_chars, config
        )
        if await store.set_generated_title(self.pool, thread.id, title, source):
            await queue.put(
                {"type": "data-title", "data": {"threadId": str(thread.id), "title": title}}
            )

    async def _save(
        self,
        thread_id: UUID,
        message_id: UUID,
        record: TurnRecord,
        status: MessageStatus,
        trace_id: str | None,
    ) -> None:
        await store.add_message(
            self.pool,
            thread_id,
            "assistant",
            record.text,
            message_id=message_id,
            queries=record.queries,
            status=status,
            trace_id=trace_id,
        )
        if trace_id:
            for name, (value, data_type) in turn_scores(record, status).items():
                langfuse().create_score(
                    trace_id=trace_id, name=name, value=value, data_type=data_type
                )
