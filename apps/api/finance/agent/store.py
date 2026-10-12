"""Chat threads and the history the user sees (spec section 8). The agent's own memory is the
LangGraph checkpoint; ChatService.delete_thread removes both."""

from uuid import UUID

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from finance.agent.models import (
    ChatMessage,
    Feedback,
    MessageStatus,
    QueryResult,
    Thread,
    TitleSource,
)

_THREAD = "id, title, title_source, created_at, updated_at"
_MESSAGE = "id, thread_id, role, content, queries, status, feedback, created_at"


class MessageNotFound(Exception):
    pass


async def create_thread(pool: AsyncConnectionPool) -> Thread:
    async with pool.connection() as conn:
        cursor = await conn.execute(f"insert into chat_threads default values returning {_THREAD}")
        return Thread(**await cursor.fetchone())


async def list_threads(pool: AsyncConnectionPool) -> list[Thread]:
    async with pool.connection() as conn:
        cursor = await conn.execute(f"select {_THREAD} from chat_threads order by updated_at desc")
        return [Thread(**row) for row in await cursor.fetchall()]


async def get_thread(pool: AsyncConnectionPool, thread_id: UUID) -> Thread | None:
    async with pool.connection() as conn:
        cursor = await conn.execute(
            f"select {_THREAD} from chat_threads where id = %s", (thread_id,)
        )
        row = await cursor.fetchone()
    return Thread(**row) if row else None


async def rename_thread(pool: AsyncConnectionPool, thread_id: UUID, title: str) -> Thread | None:
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "update chat_threads set title = %s, title_source = 'user', updated_at = now()"
            f" where id = %s returning {_THREAD}",
            (title, thread_id),
        )
        row = await cursor.fetchone()
    return Thread(**row) if row else None


async def set_generated_title(
    pool: AsyncConnectionPool, thread_id: UUID, title: str, source: TitleSource
) -> bool:
    """Store a generated title unless the thread already has one (the user may have renamed it)."""
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "update chat_threads set title = %s, title_source = %s"
            " where id = %s and title_source is null returning id",
            (title, source, thread_id),
        )
        return await cursor.fetchone() is not None


async def delete_thread(pool: AsyncConnectionPool, thread_id: UUID) -> bool:
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "delete from chat_threads where id = %s returning id", (thread_id,)
        )
        return await cursor.fetchone() is not None


async def add_message(
    pool: AsyncConnectionPool,
    thread_id: UUID,
    role: str,
    content: str,
    *,
    message_id: UUID | None = None,
    queries: list[QueryResult] = (),
    status: MessageStatus = "ok",
    trace_id: str | None = None,
) -> UUID:
    async with pool.connection() as conn, conn.transaction():
        cursor = await conn.execute(
            "insert into chat_messages (id, thread_id, role, content, queries, status,"
            " langfuse_trace_id) values (coalesce(%s, gen_random_uuid()), %s, %s, %s, %s, %s, %s)"
            " returning id",
            (
                message_id,
                thread_id,
                role,
                content,
                Jsonb([q.model_dump() for q in queries]),
                status,
                trace_id,
            ),
        )
        new_id = (await cursor.fetchone())["id"]
        await conn.execute("update chat_threads set updated_at = now() where id = %s", (thread_id,))
    return new_id


async def list_messages(pool: AsyncConnectionPool, thread_id: UUID) -> list[ChatMessage]:
    async with pool.connection() as conn:
        cursor = await conn.execute(
            f"select {_MESSAGE} from chat_messages where thread_id = %s order by created_at, id",
            (thread_id,),
        )
        return [ChatMessage(**row) for row in await cursor.fetchall()]


async def set_feedback(pool: AsyncConnectionPool, message_id: UUID, value: Feedback) -> str | None:
    """Record thumbs up or down on an answer; return its Langfuse trace id (None if untraced)."""
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "update chat_messages set feedback = %s where id = %s and role = 'assistant'"
            " returning langfuse_trace_id",
            (value, message_id),
        )
        row = await cursor.fetchone()
    if row is None:
        raise MessageNotFound(f"answer {message_id} not found")
    return row["langfuse_trace_id"]
